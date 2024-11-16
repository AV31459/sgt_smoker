import asyncio
from logging import Logger

from telethon import TelegramClient, events, functions, types

from . import context as exp_context
from . import const
from .basehandler import BaseHandler
from .clientmixin import ClientMixin
from .core import Context, get_chat_at_id_string, get_message_info_string
from .exceptions import InitError


class SmokerBotHandler(ClientMixin, BaseHandler):
    """Основой объект-хендлер бота."""

    @BaseHandler.build_context('init')
    def __init__(
            self,
            client: TelegramClient,
            logger: Logger,
            persistence_interval: int = None
    ):
        exp_context.print_vars('init')

        # Инициализация базовых аттрибутов
        super().__init__(client, logger)
        self._persistence_interval = persistence_interval
        self.loop = client.loop  # just convinience

        # Инициаизация команд бота, загрузка данных, создание задач и т.п.
        self._post_init(
            context=Context(
                _log_prefix='handler initialisation:',
                propagate_exc=True
            )
        )

    @BaseHandler.handle_exceptions
    def _post_init(self, context: Context = None):
        """Инициаизация команд бота, загрузка данных, запуск задач и т.п."""

        # Проверка, что клиент уже залогинен
        if not self.client.is_connected():
            raise InitError('telethon client is not yet connected')

        # Установка команд и кнопки меню бота
        self.loop.run_until_complete(
            self._set_bot_commands_and_menu(context=context)
        )

        # Создание задачи автосохранения данных
        self._presistence_task = self.loop.create_task(
            self._persitstence_routine()
        )

    def shutdown(self):
        """Завершение работы хендлера."""
        self.persist_data(context=Context(_log_prefix='shutting down:'))

    @BaseHandler.handle_exceptions
    async def _set_bot_commands_and_menu(self, context: Context = None):
        """Установка (списка) команд бота и кнопки меню."""

        context = Context()
        context.log_prefix = 'set default commands and menu:'

        await self._client_call(
            functions.bots.SetBotCommandsRequest(
                scope=types.BotCommandScopeUsers(),
                lang_code=const.BOT_COMMANDS_LANG_CODE,
                commands=const.BOT_COMMANDS_DEFAULT
            ),
            context=context
        )
        # raise InitFailure('Error setting default commands and menu')

    @BaseHandler.handle_exceptions
    def persist_data(self, context: Context = None):
        """Сохранить данные бота."""

        # with open('data/users_channels.yaml', 'w') as f:
        #     yaml.safe_dump(
        #         {'users': self._users, 'channels': self._channels},
        #       # f, indent=4
        #     )
        self.logger.info('BotHandler user data persisted')

    async def _persitstence_routine(self):
        """Задача периодического сохранения данных."""

        if not self._persistence_interval:
            return

        await asyncio.sleep(self._persistence_interval)
        self.persist_data(
            context=Context(
                _log_prefix='persistence routine:',
                propagate_exc=False
            )
        )

        # Пересоздаем задачу
        self.loop.create_task(self._persitstence_routine())

    def filter_message_event(self, event) -> bool:
        """Фильтрация входящих событий (обновлений) для сообщений.

        Пропускаются только приватные (private) сообщения, сервисные сообщения
        игнорируются.

        Возвращаемый тип `bool`: cобытие прошло фильтр - `True`, иначе `False`.
        """

        if event.message.action or not event.message.is_private:
            return self.logger.info(
                f'message {get_chat_at_id_string(event.message)} is either '
                'service one or not private, ignore.'
            )

        return True

    @BaseHandler._build_context
    @BaseHandler.handle_exceptions
    async def on_new_message(
        self,
        event: events.NewMessage.Event,
        context: Context = None
    ):
        """Обработчик новых входящих сообщений."""

        context.log_prefix = f'new message {context.log_prefix}'
        self.logger.info(f'{context.log_prefix} message info: '
                         f'{get_message_info_string(event.message)}')

        # while True:
        #     await asyncio.sleep(2)
        await event.respond(event.message.message)

    @BaseHandler._build_context
    @BaseHandler.handle_exceptions
    async def on_message_edited(self, event):
        """Обработчик событий редактирования сообщений."""

        self.logger.debug('on message edited')
        raise ValueError('test error')
        # await self.on_new_message('str')
        pass

    def _is_blocked_by_peer(self, context: Context = None, **kwargs):
        """Handler for UserIsBlockedError."""

        self.logger.info(
            f'{context.log_prefix} Blocked by user_id={context.chat_id}. '
            'Actions TBD.'
        )
