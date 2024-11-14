import asyncio
import functools
from abc import ABC, abstractmethod
from logging import Logger

from telethon import TelegramClient, errors
from telethon.events.common import EventCommon

from .core import Context


class BaseHandler(ABC):
    """Базовый объект-хендлер для обработки событий Телеграм."""

    def __init__(self, client: TelegramClient, logger: Logger):
        self.client = client
        self.logger = logger

    def _log_exception(
        self,
        exc: Exception,
        log_prefix: str = '',
        propagate: bool = False,
        exc_info: bool = False
    ):
        """Log an exception and optionally reraise it."""

        self.logger.error(f'{log_prefix} {exc.__class__.__name__}: {exc}',
                          exc_info=exc_info)
        if propagate:
            raise exc

    @staticmethod
    def build_context(method):
        """Декоратор для создания объекта `Context` и передачи его методу.

        Предназначен для методов, зарегистрированных в качестве обрабочиков
        событий и получающих от telethon объект `event` единственным
        позиционным агрументом.

        Создаваемый `context_obj` передается декорируемому методу
        именованным агрументом `context=context_obj`.

        ***NB!*** для использования только с асинхронными методами.
        """
        @functools.wraps(method)
        async def wrapper(self: BaseHandler, *args, **kwargs):

            if not (args and isinstance(args[0], EventCommon)):
                raise ValueError(
                    f'build_context() decorator on {method.__name__}(): '
                    'wrapped method should only be called with a telethon '
                    'event instance as a first positional argument.'
                )

            kwargs.update({'context': Context.build_from_event(args[0])})

            return await method(self, *args, **kwargs)

        return wrapper

    @staticmethod
    def handle_exceptions(method):
        """Декоратор для перехвата и обработки исключений в методах класса.

        Может быть использован как синхронными, так и ассинхронными методами.

        :experimantal: При получении FloodError засыпает на указанное число
        секунд и рекурсивно перевызывает исходный (декорированный) метод.

        Для декорированного метода обрабатываются _опциональный_ именованный
        параметр 'context' (при наличии в kwargs), для получения следующих
        аргументов:

            - `log_prefix`: str - префикс сообщения об ошибке, по умолчанию ''
            - `propagate_exc`: bool - перевызвать исключение после
            логгирования, по умолчанию False.
        """

        @functools.wraps(method)
        def wrapper(self: BaseHandler, *args, **kwargs):

            context = kwargs.get('context') or Context()
            log_prefix = context.log_prefix
            propagate_exc = context.propagate_exc
            log_prefix += (
                 f' {method.__name__}() call with args={args}, '
                 f'kwargs={kwargs}:'
            )

            if not asyncio.iscoroutinefunction(method):
                try:
                    return method(self, *args, **kwargs)
                except Exception as exc:
                    self._log_exception(
                        exc,
                        log_prefix=f'{log_prefix} 🔸',
                        propagate=propagate_exc
                    )
                return

            async def async_wrapper():
                try:
                    return await method(self, *args, **kwargs)

                # Обработка UserIsBlockedError
                except errors.UserIsBlockedError:
                    self._is_blocked_by_peer(context=context)

                # Обработка FloodWaitError
                except errors.FloodWaitError as exc:

                    # Логгируем и ждем указанное время
                    self.logger.info(
                        f'{log_prefix} 🟡 got a FloodWaitError, sleeping '
                        f'for {exc.seconds} seconds'
                    )
                    await asyncio.sleep(exc.seconds)

                    # Рекурсивно перевызываем декорированный метод
                    self.logger.info(
                        f'{log_prefix} waking up after FloodWaitError '
                        'and re-calling itself.'
                    )
                    return (
                        await getattr(self, method.__name__)(*args, **kwargs)
                    )

                except Exception as exc:
                    self._log_exception(
                        exc,
                        log_prefix=f'{log_prefix} 🔸',
                        propagate=propagate_exc
                    )

            return async_wrapper()

        return wrapper

    @abstractmethod
    def _is_blocked_by_peer(self, context: Context = None, **kwargs):
        """Abstract UserIsBlockedError handler."""
        pass
