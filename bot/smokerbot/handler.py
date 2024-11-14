import asyncio

from logging import Logger

from telethon import TelegramClient, events

from .basehandler import BaseHandler
from .clientmixin import ClientMixin
from .core import Context
from .core import get_chat_at_id_string, get_message_info_string


class SmokerBotHandler(ClientMixin, BaseHandler):
    """Основой объект-хендлер бота."""

    def __init__(
            self,
            client: TelegramClient,
            logger: Logger,
            persistence_interval: int = None
    ):
        # Клиент должен быть уже залогинен
        if not client.is_connected():
            self.logger.error(
                'BotHandler initialization error: Telegram client is '
                'not yet connected. Terminating.'
            )
            raise ValueError

        super().__init__(client, logger)
        self._persistence_interval = persistence_interval
        self.loop = client.loop  # just convinience

        # Установка команд и меню бота
        self._set_bot_commands()

        # Создание задачи автосохранения данных
        self.loop.create_task(self.persitstence_task())

    def _set_bot_commands(self):
        """Установка (списка) команд бота."""
        pass

    @BaseHandler.handle_exceptions
    def persist_data(self):
        """Сохранить данные бота."""

        # with open('data/users_channels.yaml', 'w') as f:
        #     yaml.safe_dump(
        #         {'users': self._users, 'channels': self._channels},
        #       # f, indent=4
        #     )
        self.logger.info('BotHandler user data persisted')

    async def persitstence_task(self):
        """Задача (task) периодического сохранения данных."""

        if not self._persistence_interval:
            return

        await asyncio.sleep(self._persistence_interval)
        self.persist_data()

        # Пересоздаем задачу
        self.loop.create_task(self.persitstence_task())

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

    @BaseHandler.build_context
    @BaseHandler.handle_exceptions
    async def on_new_message(
        self,
        event: events.NewMessage.Event,
        context: Context = None
    ):
        """Обработчик новых входящих сообщений."""

        if not isinstance(context, Context):
            raise ValueError('method requires \'Context\' object in kwargs.')

        context.log_prefix = f'new message {context.log_prefix}'
        self.logger.info(f'{context.log_prefix} message info: '
                         f'{get_message_info_string(event.message)}')

        # while True:
        #     await asyncio.sleep(2)
        await event.respond(event.message.message)

    @BaseHandler.build_context
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
