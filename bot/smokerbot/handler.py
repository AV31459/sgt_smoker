import asyncio
from contextvars import Context, copy_context
from logging import Logger
from pathlib import Path
from time import time

import psutil
from telethon import TelegramClient, events, functions, types

from . import const, context, helpers
from .basehandler import BaseHandler
from .clientmixin import ClientMixin
from .exceptions import ContextValuetError, InitError
from .userdatamixin import UserdataMixin


class SmokerBotHandler(UserdataMixin, ClientMixin, BaseHandler):
    """Основой объект-хендлер бота."""

    new_context = BaseHandler.new_context
    manage_context = BaseHandler.manage_context

    @new_context('init', propagate_exc=True)
    @manage_context
    def __init__(
            self,
            client: TelegramClient,
            logger: Logger,
            data_path: Path,
            admin_ids: list[int] = [],
            persistence_interval: int = None
    ):
        # Инициализация базовых аттрибутов
        super().__init__(client, logger)
        self.data_path = data_path
        self._admin_ids = admin_ids
        self._persistence_interval = persistence_interval

        # Собственный  user_id
        self._self_id = None

        # MVP: пользовательские данные словарь
        # {iser_id: UserData_obj}
        self._users = {k: self._get_default_userdata() for k in admin_ids}

        # Инициаизация команд бота, загрузка данных, создание задач и т.п.
        self._post_init()

    @manage_context
    def _post_init(self):
        """Инициаизация команд бота, загрузка данных, запуск задач и т.п."""

        # Проверка, что клиент уже залогинен
        if not self.client.is_connected():
            raise InitError('telethon client is not yet connected')

        # Получаем собственный user_id
        self._self_id = (
            self._loop.run_until_complete(
                self.client.get_me(input_peer=True)
            ).user_id
        )

        # Установка команд и кнопки меню бота
        self._loop.run_until_complete(
            self._set_bot_commands_and_menu()
        )

        # Загрузка пользовательских данных
        self._load_userdata()

        # Проверка данных, запуск прерванных таймеров, если возможно
        self._loop.run_until_complete(
            self._data_check_and_timer_restart()
        )

        # Создание задачи автосохранения данных
        self._presistence_task = self._loop.create_task(
            self._persitstence_task()
        )

    @manage_context
    async def _data_check_and_timer_restart(self):
        """Проверка данных, пересоздание таймеров, если возможно."""

        # Temporary disabling excaption propageation
        token = context.propagate_exc.set(False)

        # NB: Iterating over copy() to be able to delete some keys
        for user_id in self._users.copy():

            userdata = self._users[user_id]

            # Если бот был заблокирован - удаляем данные
            if not userdata.is_active_user:
                self._users.pop(user_id)

            # Получаем от клиента информацию о пользователе
            if (
                not (user := await self._get_entity(user_id))
                and isinstance(user, types.User)
            ):
                self.logger.warning(
                    f'{context.get_task_prefix()} unable to get user info '
                    f'from Telegram for user_id={user_id}'
                )
                userdata.is_running = False
                continue

            # Informing admin that bot is being restarted
            if user_id in self._admin_ids:
                await self._send_message(user, const.MSG_ADMIN_ON_INIT)

            # Запущенного таймера нет
            if not (userdata.is_running and userdata.is_timer):
                continue

            # Если время еще не вышло, пересоздаем таймер
            if time() < userdata.timer_end:
                self.logger.info(
                    f'{context.get_task_prefix()} re-setting timer '
                    f'for user_id={user_id}'
                )
                self._set_timer(user_id, user, userdata.timer_end)
                continue

            # Время таймера вышло - сообщаем пользователю об ошибке
            userdata.is_running = False
            userdata.is_timer = False
            self.logger.info(
                f'{context.get_task_prefix()} expired timer for '
                f'user_id={user_id}, informing user on error'
            )
            await self._send_message(user, const.MSG_ERROR_CHECK_SETTINGS)

        context.propagate_exc.reset(token)

        self.logger.info(
            f'{context.get_task_prefix()} User data check completed'
        )

    @new_context('persistence')
    @manage_context
    async def _persitstence_task(self):
        """Задача периодического сохранения данных."""

        if not self._persistence_interval:
            return

        await asyncio.sleep(self._persistence_interval)
        self._save_userdata()

        # Пересоздаем задачу
        self._loop.create_task(self._persitstence_task())

    @new_context()
    @manage_context
    def shutdown(self):
        """Завершение работы хендлера."""

        self._save_userdata()

    @manage_context
    async def _set_bot_commands_and_menu(self):
        """Установка (списка) команд бота и кнопки меню."""

        await self._client_call(
            functions.bots.SetBotCommandsRequest(
                scope=types.BotCommandScopeUsers(),
                lang_code=const.BOT_COMMANDS_LANG_CODE,
                commands=const.BOT_COMMANDS_DEFAULT
            ),
        )

        await self._client_call(
            functions.bots.SetBotMenuButtonRequest(
                user_id=types.InputUserEmpty(),
                button=types.BotMenuButtonCommands(),
            )
        )

    @new_context('filter event', event_handling=True)
    @manage_context
    def filter_event(
        self,
        event: events.NewMessage.Event | events.CallbackQuery.Event
    ) -> bool:
        """Фильтрация входящих событий (обновлений).

        Пропускаются только следующие события `telethon`:
        - `NewMessage` - новое сообщение, если оно является приватным
        (private), сервисные сообщения игнорируются.
        - `CallbackQuery` - callback-запросы из чатов, `via_inline` запросы
        игнорируются.

        Возвращаемый тип `bool`: cобытие прошло фильтр - `True`, иначе `False`.
        """

        # Новое сообщение
        if (isinstance(event, events.NewMessage.Event)):

            if (event.message.is_private and not event.message.action):
                return True

            # NB: logger.info() returns None
            return bool(self.logger.info(
                f'{context.get_task_prefix()} message is either '
                'service one or not private, ignore.'
            ))

        # callback-запрос
        return (
            (
                isinstance(event, events.CallbackQuery.Event)
                and not event.via_inline
            )
            or False
        )

    @new_context('new message', event_handling=True)
    @manage_context
    async def on_new_message(self, event):
        """Обработчик новых входящих сообщений."""

        # Проверка контекста
        await self._check_contextvars(extra_vars=('msg',))

        self._get_or_create_userdata().last_seen = time()

        self.logger.info(
            f'{context.get_task_prefix()} message info: '
            f'{helpers.get_message_info_string(msg := context.msg.get())}'
        )

        # Если сообщение содержит команду, вызываем соответсвующий обработчик
        if (
            (command := helpers.get_command_from_string(msg.message))
            and (command_name := command.pop('name'))
            and (handler := getattr(self, f'_on_command_{command_name}'))
        ):
            return await handler(**command)

        # Сообщаем, что не поняли, что хочет пользователь
        await self._set_reaction_not_understood()

    @manage_context
    async def _on_command_start(self, **kwargs):
        """Обработчик команды /start."""

        # Устанавливаем признак активности пользователя
        self._get_or_create_userdata().is_active_user = True

        user = context.sender.get()

        await self._send_message(
            user,
            const.MSG_START.format(name=user.first_name)
        )

        self.logger.info(
            f'{context.get_task_prefix()} /start command handled '
            f'{const.EMOJI_OK}'
        )

    @manage_context
    async def _on_command_help(self, **kwargs):
        """Обработчик команды /help."""

        await self._send_message(context.sender.get(), const.MSG_HELP)

        self.logger.info(
            f'{context.get_task_prefix()} '
            f'/help command handled {const.EMOJI_OK}'
        )

    @manage_context
    async def _on_command_settings(self, **kwargs):
        """Обработчик команды /settings."""

        await self._send_message(
            context.sender.get(),
            self._get_settings_string()
        )
        self.logger.info(
            f'{context.get_task_prefix()} /settings command handled '
            f'{const.EMOJI_OK}'
        )

    @manage_context
    async def _on_command_setmode(self, **kwargs):
        """Обработчик команды /setmode."""

        userdata = self._get_or_create_userdata()

        # Если получили явное значение 'mode'
        if (mode := kwargs.get('mode')):

            userdata.mode = mode

            await self._send_message(
                context.sender.get(),
                const.MSG_SETTING_SUCCESS_PREFIX + self._get_settings_string()
            )
            return self.logger.info(
                f'{context.get_task_prefix()} /setmode command handled '
                f'{const.EMOJI_OK}'
            )

        # Установка с помощью кнопок
        message, buttons = self._build_setmode_msg(userdata.mode)

        await self._send_message(
            context.sender.get(),
            message,
            buttons=buttons
        )

    @manage_context
    async def _on_command_setinterval(self, **kwargs):
        """Обработчик команды /setinterval."""

        userdata = self._get_or_create_userdata()

        # Если получили явное значение 'interval'
        if (interval := kwargs.get('interval')):

            userdata.interval = interval

            await self._send_message(
                context.sender.get(),
                const.MSG_SETTING_SUCCESS_PREFIX + self._get_settings_string()
            )
            return self.logger.info(
                f'{context.get_task_prefix()} /setinterval command handled '
                f'{const.EMOJI_OK}'
            )

        # Установка с помощью кнопок
        message, buttons = self._build_setinterval_msg(userdata.interval)

        await self._send_message(
            context.sender.get(),
            message,
            buttons=buttons
        )

    @manage_context
    async def _on_command_setinitial(self, **kwargs):
        """Обработчик команды /setinitial."""

        userdata = self._get_or_create_userdata()

        # Если получили явное значение 'initial_sig'
        if (initial_sig := kwargs.get('initial_sig')):

            userdata.initial_sig = initial_sig

            await self._send_message(
                context.sender.get(),
                const.MSG_SETTING_SUCCESS_PREFIX + self._get_settings_string()
            )
            return self.logger.info(
                f'{context.get_task_prefix()} /setinitial command handled '
                f'{const.EMOJI_OK}'
            )

        # Установка с помощью кнопок
        message, buttons = self._build_setinitial_msg(userdata.initial_sig)

        await self._send_message(
            context.sender.get(),
            message,
            buttons=buttons
        )

    @manage_context
    async def _on_command_settz(self, **kwargs):
        """Обработчик команды /settz."""

        userdata = self._get_or_create_userdata()

        # Если получили явное значение 'tz_offset'
        if (tz_offset := kwargs.get('tz_offset')):

            userdata.tz_offset = tz_offset

            await self._send_message(
                context.sender.get(),
                const.MSG_SETTING_SUCCESS_PREFIX + self._get_settings_string()
            )
            return self.logger.info(
                f'{context.get_task_prefix()} /settz command handled '
                f'{const.EMOJI_OK}'
            )

        # Установка с помощью кнопок
        message, buttons = self._build_settz_msg(userdata.tz_offset)

        await self._send_message(
            context.sender.get(),
            message,
            buttons=buttons
        )

    @manage_context
    async def _on_command_status(self, **kwargs):
        """Обработчик команды /status."""

        await self._send_status_msg()

        self.logger.info(
            f'{context.get_task_prefix()} /status command handled '
            f'{const.EMOJI_OK}'
        )

    @manage_context
    async def _on_command_run(self, **kwargs):
        """Обработчик команды /run."""

        userdata = self._get_or_create_userdata()
        log_success_string = (
            f'{context.get_task_prefix()} /run command handled '
            f'{const.EMOJI_OK}'
        )

        # Если сервис уже запущен, просто сообщаем об этом
        if userdata.is_running:

            await self._send_message(
                context.sender.get(),
                const.MSG_RUN_ALREADY_RUNNING
            )
            return self.logger.info(log_success_string + ': alredy running')

        userdata.is_running = True
        userdata.ran_at = time()
        userdata.sig_available = userdata.initial_sig
        userdata.sig_smoked = 0

        # Ручной режим, есть доступные сигареты -> таймер на паузу
        if userdata.mode == 'manual' and userdata.sig_available > 0:

            userdata.is_timer = False
            await self._send_status_msg()
            return self.logger.info(log_success_string + ': timer on pause')

        # Запуск таймера
        self._set_timer()
        await self._send_status_msg()
        return self.logger.info(log_success_string + ': timer started')

    @manage_context
    async def _on_command_stop(self, **kwargs):
        """Обработчик команды /stop."""

        userdata = self._get_or_create_userdata()

        # Если сервис запущен - останавливаем таймер
        # и сообщаем о кол-ве выкупенных сигарет
        if userdata.is_running:
            userdata.is_running = False

            # Останавливаем таймер
            if userdata.is_timer:
                await self._cancel_task_by_name(
                    helpers.get_wakeup_task_name(context.sender_id.get())
                )

            await self._send_message(
                context.sender.get(),
                const.MSG_STOP_SMOKED_CIGS.format(
                    sig_smoked=userdata.sig_smoked
                )
                + (
                    const.MSG_STOP_AVG_INTEVAL.format(
                        avg_intrerval=(helpers.get_timedelta_string(
                            (time() - userdata.ran_at)
                            / (userdata.sig_smoked - 1)
                        ))
                    )
                    if (userdata.sig_smoked > 1)
                    else ''
                )
            )

        await self._send_status_msg()
        self.logger.info(
            f'{context.get_task_prefix()} '
            f'/stop command handled {const.EMOJI_OK}'
        )

    @manage_context
    async def _on_command_smoke(self, **kwargs):
        """Обработчик команды /smoke."""

        userdata = self._get_or_create_userdata()
        log_success_string = (
            f'{context.get_task_prefix()} /smoke command handled '
            f'{const.EMOJI_OK}'
        )

        # Сервис остановелен или нет доступных сигарет - отказ
        if (
            (
                not userdata.is_running
                and (reply := const.MSG_SMOKE_NEGATIVE_STOPPED)
            )
            or (
                userdata.sig_available < 1
                and (reply := const.MSG_SMOKE_NEGATIVE_NO_SIG_AVAILABLE)
            )
        ):
            await self._send_message(context.sender.get(), reply)
            return self.logger.info(log_success_string)

        userdata.sig_available -= 1
        userdata.sig_smoked += 1

        # Если режим ручной, и кол-во доступных сигарет == 0
        # то запускаем таймер
        if userdata.mode == 'manual' and userdata.sig_available == 0:
            self._set_timer()

        await self._send_message(
            context.sender.get(),
            const.MSG_SMOKE_AFFIRMATIVE
        )
        await self._send_status_msg()
        self.logger.info(log_success_string)

    @manage_context
    async def _on_command_info(self, **kwargs):
        """Обработчик команды администратора /info."""

        # Доступно только администратору бота
        if context.sender_id.get() not in self._admin_ids:
            await self._set_reaction_not_understood()

        time_now = time()

        await self._send_message(
            context.sender.get(),
            const.MSG_INFO.format(
                n_users=len([
                    user_id for user_id, userdata in self._users.items()
                    if (
                        # пользователь не блокировал бота
                        userdata.is_active_user
                        # был активен менее чем неделю назад
                        and (
                            (time_now - userdata.last_seen)
                            < const.SECONDS_IN_WEEK
                        )
                    )
                ]),
                mem_mb=(psutil.Process().memory_info().rss / (1024 ** 2))
            )
        )

        self.logger.info(
            f'{context.get_task_prefix()} '
            f'/info command handled {const.EMOJI_OK}'
        )

    @new_context('callback query', event_handling=True)
    @manage_context
    async def on_callback_query(self, event: events.CallbackQuery.Event):
        """Обработчик событий callback query."""

        # Проверка контекста
        await self._check_contextvars(extra_vars=('query_data',))

        self._get_or_create_userdata().last_seen = time()

        # Подтверждаем получение
        await event.answer()

        decoded_data = context.query_data.get().decode('utf-8')

        self.logger.info(
            f'{context.get_task_prefix()} callback data: \'{decoded_data}\''
        )

        # Если сообщение содержит команду, вызываем соответсвующий обработчик
        if (
            (command := helpers.get_callback_command_from_string(decoded_data))
            and (command_name := command.pop('name'))
            and (handler := getattr(self, f'_on_callback_{command_name}'))
        ):
            return await handler(**command)

    @manage_context
    async def _on_callback_status_update(self):
        """Сallback `status_update`: обновить сообщение со статусом."""

        message, buttons = self._build_status_msg()

        await self._edit_message(
            context.sender.get(),
            context.msg_id.get(),
            text=message,
            buttons=buttons
        )

    @manage_context
    async def _on_callback_setinterval(self, **kwargs):
        """Сallback `setinterval`: изменить/установить значение `interval`."""

        # Установка значения
        if kwargs.get('action') == 'set':

            # Удаляем техническое сообщение
            await self._delete_messages(
                context.sender.get(),
                context.msg_id.get()
            )

            # Выполняем обычную команду установки значения
            return await self._on_command_setinterval(
                interval=kwargs['interval']
            )

        # Изменение значения (до установки) - обновляем техническое сообщение
        message, buttons = self._build_setinterval_msg(kwargs['interval'])

        await self._edit_message(
            context.sender.get(),
            context.msg_id.get(),
            text=message,
            buttons=buttons
        )

        return self.logger.info(
            f'{context.get_task_prefix()} callback \'setinterval\' handled '
            f'{const.EMOJI_OK}'
        )

    @manage_context
    async def _on_callback_setmode(self, **kwargs):
        """Сallback `setmode`: изменить/установить значение `mode`."""

        # Установка значения
        if kwargs.get('action') == 'set':

            # Удаляем техническое сообщение
            await self._delete_messages(
                context.sender.get(),
                context.msg_id.get()
            )

            # Выполняем обычную команду установки значения
            return await self._on_command_setmode(mode=kwargs['mode'])

        # Изменение значения (до установки) - обновляем техническое сообщение
        message, buttons = self._build_setmode_msg(kwargs['mode'])

        await self._edit_message(
            context.sender.get(),
            context.msg_id.get(),
            text=message,
            buttons=buttons
        )

        self.logger.info(
            f'{context.get_task_prefix()} callback \'setmode\' handled '
            f'{const.EMOJI_OK}'
        )

    @manage_context
    async def _on_callback_setinitial(self, **kwargs):
        """Сallback `setinitial`: изменить/установить `initial_sig`."""

        # Установка значения
        if kwargs.get('action') == 'set':

            # Удаляем техническое сообщение
            await self._delete_messages(
                context.sender.get(),
                context.msg_id.get()
            )

            # Выполняем обычную команду установки значения
            return await self._on_command_setinitial(
                initial_sig=kwargs['initial_sig']
            )

        # Изменение значения (до установки) - обновляем техническое сообщение
        message, buttons = self._build_setinitial_msg(kwargs['initial_sig'])

        await self._edit_message(
            context.sender.get(),
            context.msg_id.get(),
            text=message,
            buttons=buttons
        )

        self.logger.info(
            f'{context.get_task_prefix()} callback \'setinitial\' handled '
            f'{const.EMOJI_OK}'
        )

    @manage_context
    async def _on_callback_settz(self, **kwargs):
        """Сallback `settz`: изменить/установить значение `tz_offset`."""

        # Установка значения
        if kwargs.get('action') == 'set':

            # Удаляем техническое сообщение
            await self._delete_messages(
                context.sender.get(),
                context.msg_id.get()
            )

            # Выполняем обычную команду установки значения
            return await self._on_command_settz(tz_offset=kwargs['tz_offset'])

        # Изменение значения (до установки) - обновляем техническое сообщение
        message, buttons = self._build_settz_msg(kwargs['tz_offset'])

        await self._edit_message(
            context.sender.get(),
            context.msg_id.get(),
            text=message,
            buttons=buttons
        )

        self.logger.info(
            f'{context.get_task_prefix()} callback \'settz\' handled '
            f'{const.EMOJI_OK}'
        )

    @manage_context
    async def _on_blocked_by_peer(self):
        """Обработка события (exception) блокировки бота пользователем."""

        user_id = context.sender_id.get()
        userdata = self._get_or_create_userdata(user_id)

        userdata.is_active_user = False
        userdata.is_running = False

        # Останавливаем таймер
        if userdata.is_timer:
            await self._cancel_task_by_name(
                helpers.get_wakeup_task_name(user_id)
            )

        self.logger.info(
            f'{context.get_task_prefix()} Blocked by user_id='
            f'{user_id}. Timer is stopped.'
        )

    @manage_context
    async def _set_reaction_not_understood(self) -> None:
        """Установить для сообщения в контексте emoji реакцию: 'не понял'."""

        await self._set_reaction_emoji(const.EMOJI_SHRUG)
        self.logger.info(
            f'{context.get_task_prefix()} {const.EMOJI_SHRUG[0]} '
            'not understood'
        )

    # NB: no @manage_context here as exceptions to be handled by caller
    async def _check_contextvars(
            self,
            extra_vars: tuple[str] = ()
    ) -> bool:
        """Проверить контекст, получить недостающие переменные.

        Проверка наличия  в контексте обязательных {`chat_id`, `sender_id`,
        `msg_id`, `event`} и дополенительных переменных, переданных
        в`extra_vars`.

        При необходимости, получить `sender`, `chat`.

        В случе ошибки вызвает `ContextValuetError`.
        """

        contextvar_names = tuple(v.name for v in copy_context().keys())

        for var_name in (
            ('chat_id', 'sender_id', 'msg_id', 'event') + extra_vars
        ):
            if var_name not in contextvar_names:
                raise ContextValuetError(
                    f'missing requred \'{var_name}\' in context'
                )

        if (
            not (sender := context.sender.get())
            or not isinstance(sender, types.User)
        ):
            # Пытаемся получить 'sender' отдельным запросом
            sender = await self._get_entity(context.sender_id.get())

            if not isinstance(sender, types.User):
                raise ContextValuetError(
                    'unable to fetch \'sender\' in context'
                )

            context.sender.set(sender)

    @manage_context
    def _build_status_msg(
        self
    ) -> tuple[str, list[list[types.KeyboardButtonCallback]] | None]:
        """Сформировать сообщение с текущим статусом таймера пользователя.

        Возвращает кортеж: `(message, callback_buttons)`
        """

        userdata = self._get_or_create_userdata()

        if not userdata.is_running:
            return (const.MSG_STATUS_STOPPED, None)

        buttons = [[
            types.KeyboardButtonCallback(
                text=const.CALLBACK_BTN_TEXT_UPDATE,
                data=const.CALLBACK_COMMAND_STATUS_UPDATE.encode('utf-8')
            )
        ]]

        if not userdata.is_timer:
            return (
                const.MSG_STATUS_PAUSED.format(
                    sig_available=userdata.sig_available,
                    colored_circle=(
                        const.EMOGI_GREEN_CIRCLE if userdata.sig_available
                        else const.EMOGI_YELLOW_CIRCLE
                    ),
                    now=helpers.get_time_string(time(), userdata.tz_offset)
                ),
                buttons
            )

        return (
            const.MSG_STATUS_RUNNING.format(
                sig_available=userdata.sig_available,
                colored_circle=(
                        const.EMOGI_GREEN_CIRCLE if userdata.sig_available
                        else const.EMOGI_YELLOW_CIRCLE
                ),
                timer_end=helpers.get_time_string(
                    userdata.timer_end, userdata.tz_offset
                ),
                time_remaining=helpers.get_timedelta_string(
                    userdata.timer_end - time()
                ),
                now=helpers.get_time_string(time(), userdata.tz_offset)
            ),
            buttons
        )

    @manage_context
    def _build_setinterval_msg(
        self,
        interval: int
    ) -> tuple[str, list[list[types.KeyboardButtonCallback]] | None]:
        """Сформировать техническое сообщение установки значения `setinterval`.

        Возвращает кортеж: `(message, callback_buttons)`
        """

        buttons = [
            [
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_MINUS_10,
                    data=const.CALLBACK_COMMAND_SETINTERVAL.format(
                        action='adjust',
                        interval=max(interval - 10, const.INTERVAL_MIN)
                    ).encode('utf-8')
                ),
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_MINUS_1,
                    data=const.CALLBACK_COMMAND_SETINTERVAL.format(
                        action='adjust',
                        interval=max(interval - 1, const.INTERVAL_MIN)
                    ).encode('utf-8')
                ),
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_PLUS_1,
                    data=const.CALLBACK_COMMAND_SETINTERVAL.format(
                        action='adjust',
                        interval=min(interval + 1, const.INTERVAL_MAX)
                    ).encode('utf-8')
                ),
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_PLUS_10,
                    data=const.CALLBACK_COMMAND_SETINTERVAL.format(
                        action='adjust',
                        interval=min(interval + 10, const.INTERVAL_MAX)
                    ).encode('utf-8')
                ),
            ],
            [
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_SET,
                    data=const.CALLBACK_COMMAND_SETINTERVAL.format(
                        action='set',
                        interval=interval
                    ).encode('utf-8')
                ),
            ]
        ]

        return const.MSG_SETINTERVAL.format(interval=interval), buttons

    @manage_context
    def _build_setmode_msg(
        self,
        mode: str
    ) -> tuple[str, list[list[types.KeyboardButtonCallback]] | None]:
        """Сформировать техническое сообщение установки значения `setmode`.

        Возвращает кортеж: `(message, callback_buttons)`
        """

        buttons = [
            [
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_AUTO,
                    data=const.CALLBACK_COMMAND_SETMODE.format(
                        action='adjust',
                        mode='auto'
                    ).encode('utf-8')
                ),
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_MANUAL,
                    data=const.CALLBACK_COMMAND_SETMODE.format(
                        action='adjust',
                        mode='manual'
                    ).encode('utf-8')
                ),
            ],
            [
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_SET,
                    data=const.CALLBACK_COMMAND_SETMODE.format(
                        action='set',
                        mode=mode
                    ).encode('utf-8')
                ),
            ]
        ]

        return (
            const.MSG_SETMODE.format(
                mode=(
                    const.STR_MODE_AUTO if mode == 'auto'
                    else const.STR_MODE_MANUAL
                )
            ),
            buttons
        )

    @manage_context
    def _build_setinitial_msg(
        self,
        initial_sig: int
    ) -> tuple[str, list[list[types.KeyboardButtonCallback]] | None]:
        """Сформировать техническое сообщение установки значения `setinitial`.

        Возвращает кортеж: `(message, callback_buttons)`
        """

        buttons = [
            [
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_MINUS_1,
                    data=const.CALLBACK_COMMAND_SETINITIAL.format(
                        action='adjust',
                        initial_sig=max(initial_sig - 1, const.INITIAL_SIG_MIN)
                    ).encode('utf-8')
                ),
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_PLUS_1,
                    data=const.CALLBACK_COMMAND_SETINITIAL.format(
                        action='adjust',
                        initial_sig=min(initial_sig + 1, const.INITIAL_SIG_MAX)
                    ).encode('utf-8')
                ),
            ],
            [
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_SET,
                    data=const.CALLBACK_COMMAND_SETINITIAL.format(
                        action='set',
                        initial_sig=initial_sig
                    ).encode('utf-8')
                ),
            ]
        ]

        return const.MSG_SETINITIAL.format(initial_sig=initial_sig), buttons

    @manage_context
    def _build_settz_msg(
        self,
        tz_offset: int
    ) -> tuple[str, list[list[types.KeyboardButtonCallback]] | None]:
        """Сформировать техническое сообщение установки значения `settz`.

        Возвращает кортеж: `(message, callback_buttons)`
        """

        buttons = [
            [
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_MINUS_1,
                    data=const.CALLBACK_COMMAND_SETTZ.format(
                        action='adjust',
                        tz_offset=max(tz_offset - 1, const.TZ_OFFSET_MIN)
                    ).encode('utf-8')
                ),
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_PLUS_1,
                    data=const.CALLBACK_COMMAND_SETTZ.format(
                        action='adjust',
                        tz_offset=min(tz_offset + 1, const.TZ_OFFSET_MAX)
                    ).encode('utf-8')
                ),
            ],
            [
                types.KeyboardButtonCallback(
                    text=const.CALLBACK_BTN_TEXT_SET,
                    data=const.CALLBACK_COMMAND_SETTZ.format(
                        action='set',
                        tz_offset=tz_offset
                    ).encode('utf-8')
                ),
            ]
        ]

        return const.MSG_SETTZ.format(tz_offset=tz_offset), buttons

    @manage_context
    async def _send_status_msg(self):
        """Отправить сообщение со статусом сервиса."""

        message, buttons = self._build_status_msg()

        await self._send_message(
            context.sender.get(),
            message,
            buttons=buttons
        )

    @manage_context
    def _set_timer(
        self,
        user_id: int | None = None,
        user: types.User | None = None,
        timer_end: float | None = None
    ):
        """Создать отложенную задачу проверки таймера (wakeup).

        Если аргументы `user_id`, `user`, `timer_end` не переданы, используются
        значения/настройки из текущего контекста.
        """

        user_id = user_id or context.sender_id.get()
        userdata = self._get_or_create_userdata(user_id)
        time_now = time()

        wakeup_in_seconds = (
            timer_end - time_now if timer_end
            else userdata.interval * const.SECONDS_IN_MINUTE
        )
        userdata.is_timer = True
        userdata.timer_start = time_now
        userdata.timer_end = time_now + wakeup_in_seconds

        task_name = helpers.get_wakeup_task_name(user_id)

        # Создаем новый контекст для wakeup call
        ctx = Context()
        ctx.run(
            context.init_contextvars,
            task_name_val=task_name,
            sender_id_val=user_id,
            sender_val=(user or context.sender.get()),
        )

        self.logger.info(
            f'{context.get_task_prefix()} creating task [ {task_name} ]'
        )

        # Создаем задачу в новом контексте
        self._loop.create_task(
            self._wakeup_task(wakeup_in_seconds),
            name=task_name,
            context=ctx
        )

    @manage_context
    async def _wakeup_task(self, wakeup_in_seconds: float):
        """Задача проверки таймера чрез заданное время (wakeup)."""

        self.logger.debug(
            f'{context.get_task_prefix()} timer is set, sleeping '
            f'{wakeup_in_seconds:.1f} seconds'
        )
        await asyncio.sleep(wakeup_in_seconds)

        userdata = self._get_or_create_userdata()
        time_now = time()

        if (
            not userdata.is_running           # сервис остановлен
            or not userdata.is_timer          # или таймер остановден
            or not userdata.timer_end         # или не установлено время
            or time_now < userdata.timer_end  # или слишком рано
            # или слишком поздно
            or time_now > userdata.timer_end + wakeup_in_seconds
        ):
            userdata.is_running = False
            userdata.is_timer = False
            await self._send_message(
                context.sender.get(),
                const.MSG_ERROR_CHECK_SETTINGS
            )
            return

        # Увеличиваем кол-во доступных сигарет
        userdata.sig_available += 1

        await self._send_message(
            context.sender.get(),
            const.MSG_NEW_CIG_AVALABLE.format(
                sig_available=userdata.sig_available
            )
        )

        self.logger.debug(f'{context.get_task_prefix()} new sig masg sent.')

        # В режиме 'manual' таймер не перезапускаем
        if userdata.mode == 'manual':
            userdata.is_timer = False
            return self.logger.debug(
                f'{context.get_task_prefix()} timer is stopped'
            )

        # В режиме 'auto' перезапускаем
        wakeup_in_seconds = userdata.interval * const.SECONDS_IN_MINUTE
        userdata.timer_start = userdata.timer_end
        userdata.timer_end = userdata.timer_start + wakeup_in_seconds

        # Новый контекст не создаем - все, что нужно есть в текущем
        self._loop.create_task(
            self._wakeup_task(wakeup_in_seconds),
            name=context.task_name.get()
        )

    @manage_context
    async def _cancel_task_by_name(self, name: str):
        """Отменить все asyncio задачи с заданным именем для текущего loop."""

        for task in (
            task for task in asyncio.all_tasks(self._loop)
            if task.get_name() == name and task.cancel()
        ):

            self.logger.debug(
                f'{context.get_task_prefix()} awaiting cancellation of '
                f'task [ {task.get_name()} ]'
            )

            try:
                await task
            except asyncio.CancelledError:
                self.logger.info(
                    f'{context.get_task_prefix()} task [ {task.get_name()} ]'
                    ' is cancelled 🔵'
                )
                # if the task is being cancelled from within itself
                if context.task_name.get() == name:
                    raise
