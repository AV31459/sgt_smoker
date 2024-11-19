import asyncio
from logging import Logger

from telethon import TelegramClient, events, functions, types

from . import const, context
from .basehandler import BaseHandler
from .clientmixin import ClientMixin
from .exceptions import InitError
from .helpers import get_message_info_string


class SmokerBotHandler(ClientMixin, BaseHandler):
    """Основой объект-хендлер бота."""

    new_context = BaseHandler.new_context
    manage_context = BaseHandler.manage_context

    @new_context(scope='init', propagate_exc=True)
    @manage_context
    def __init__(
            self,
            client: TelegramClient,
            logger: Logger,
            persistence_interval: int = None
    ):
        # Инициализация базовых аттрибутов
        super().__init__(client, logger)
        self._persistence_interval = persistence_interval

        # Инициаизация команд бота, загрузка данных, создание задач и т.п.
        self._post_init()

    @manage_context
    def _post_init(self):
        """Инициаизация команд бота, загрузка данных, запуск задач и т.п."""

        # Проверка, что клиент уже залогинен
        if not self.client.is_connected():
            raise InitError('telethon client is not yet connected')

        # Установка команд и кнопки меню бота
        self._loop.run_until_complete(
            self._set_bot_commands_and_menu()
        )

        # Создание задачи автосохранения данных
        self._presistence_task = self._loop.create_task(
            self._persitstence_routine()
        )

    @new_context()
    @manage_context
    def shutdown(self):
        """Завершение работы хендлера."""
        self.persist_data()

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

    @manage_context
    def persist_data(self):
        """Сохранить данные бота."""

        # with open('data/users_channels.yaml', 'w') as f:
        #     yaml.safe_dump(
        #         {'users': self._users, 'channels': self._channels},
        #       # f, indent=4
        #     )

        # raise ValueError('test')
        self.logger.info('BotHandler user data persisted')

    @new_context(scope='persistence')
    @manage_context
    async def _persitstence_routine(self):
        """Задача периодического сохранения данных."""

        if not self._persistence_interval:
            return

        await asyncio.sleep(self._persistence_interval)
        self.persist_data()

        # Пересоздаем задачу
        self._loop.create_task(self._persitstence_routine())

    @new_context(scope='filter message', event_handling=True)
    @manage_context
    def filter_message_event(self, event) -> bool:
        """Фильтрация входящих событий (обновлений) для сообщений.

        Пропускаются только приватные (private) сообщения, сервисные сообщения
        игнорируются.

        Возвращаемый тип `bool`: cобытие прошло фильтр - `True`, иначе `False`.
        """

        if event.message.action or not event.message.is_private:
            return self.logger.info(
                f'{context.build_log_prefix()} message is either '
                'service one or not private, ignore.'
            )

        return True

    @new_context(scope='new message', event_handling=True)
    @manage_context
    async def on_new_message(
        self,
        event: events.NewMessage.Event,
    ):
        """Обработчик новых входящих сообщений."""

        self.logger.info(
            f'{context.scope.get()} message info: '
            f'{get_message_info_string(event.message)}'
        )

        self.func_a()

        while True:
            await asyncio.sleep(2)
            await event.respond(event.message.message)

    @new_context(scope='edited message', event_handling=True)
    @manage_context
    async def on_message_edited(self, event):
        """Обработчик событий редактирования сообщений."""

        self.logger.debug('on message edited')
        raise ValueError('test error')
        # await self.on_new_message('str')
        pass

    @manage_context
    def _is_blocked_by_peer(self):
        """Handler for UserIsBlockedError."""

        raise ValueError('test')

        self.logger.info(
            f'{context.build_log_prefix()} Blocked by user_id='
            f'{context.chat_id.get()}. Actions TBD.'
        )
