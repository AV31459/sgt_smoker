import asyncio
import functools
from abc import ABC, abstractmethod
from contextvars import Context, copy_context
from logging import Logger

from telethon import TelegramClient, errors
from telethon.events.common import EventCommon

from . import context


class BaseHandler(ABC):
    """Базовый объект-хендлер для обработки событий Телеграм."""

    def __init__(self, client: TelegramClient, logger: Logger):
        self.client = client
        self.logger = logger
        self._loop = client.loop  # just convinience

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
    def build_context(
        scope: str,
        event_handling: bool = False,
        propagate_exc: bool = False
    ):
        """Декоратор для создания отдельного контекста выполнения метода.

        Может быть использован как синхронными, так и ассинхронными методами.

        Параметры:
            - `scope`- обязательное имя (область) создаваемого контекста
            - `event_handling` - декорируемый метод является обработчиком
            событий telethon, т.е. получает единственный аргумент типа
            `telethon.events.common.EventCommon`
            - `propagate_exc` - перевызовать необрабатываемые исключения после
            логгирования.

        NB: при использовании нескольких декораторов, должен быть самым
        последним (верхний уровень).
        """

        def build_context_obj(method, self, args, kwargs) -> Context:
            """Common logic for both sync and async decorators."""

            if (
                event_handling
                and not (len(args) == 1 and isinstance(args[0], EventCommon))
            ):
                self._log_exception(
                    ValueError(
                        f'{context.build_log_prefix(method, args, kwargs)} '
                        'Method was decorated as \'event_handling\', so it '
                        'must be called with single positional argument '
                        'of telethone \'Event\' type'
                    ),
                    log_prefix='context build error:',
                    propagate=True
                )

            return copy_context().run(
                context.build_context,
                scope_val=scope,
                event_val=(args[0] if event_handling else None),
                propagate_exc_val=propagate_exc
            )

        def decorator(method):

            if not asyncio.iscoroutinefunction(method):
                # Синхронный декоратор
                @functools.wraps(method)
                def sync_wrapper(self: BaseHandler, *args, **kwargs):

                    return (
                        build_context_obj(method, self, args, kwargs)
                        .run(method, self, *args, **kwargs)
                    )

                return sync_wrapper

            # Асинхронный декоратор
            @functools.wraps(method)
            async def async_wrapper(self: BaseHandler, *args, **kwargs):

                return self._loop.create_task(
                    method(self, *args, **kwargs),
                    context=build_context_obj(method, self, args, kwargs)
                )

            return async_wrapper

        return decorator

    @staticmethod
    def handle_exceptions(method):
        """Декоратор для перехвата и обработки исключений в методах класса.

        Может быть использован как синхронными, так и ассинхронными методами.

        *experimental* При получении FloodError засыпает на указанное число
        секунд и рекурсивно перевызывает исходный (декорированный) метод.

        Использует следующие переменные контекста:

            - {`scope`, `chat_id`, `msg_id`} - для формирования префикса
            логгирования ошибки
            - `propagate_exc`: bool - перевызывать ли исключение после
            логгирования
        """

        if not asyncio.iscoroutinefunction(method):

            # Синхронный декоратор
            @functools.wraps(method)
            def sync_wrapper(self: BaseHandler, *args, **kwargs):
                try:
                    return method(self, *args, **kwargs)
                except Exception as exc:
                    self._log_exception(
                        exc,
                        f'{context.build_log_prefix(method, args, kwargs)} 🔸',
                        propagate=context.propagate_exc.get()
                    )

            return sync_wrapper

        # Асинхронный декоратор
        @functools.wraps(method)
        async def async_wrapper(self: BaseHandler, *args, **kwargs):

            log_prefix = context.build_log_prefix(method, args, kwargs)

            try:
                return await method(self, *args, **kwargs)

            # Обработка UserIsBlockedError
            except errors.UserIsBlockedError:
                self._is_blocked_by_peer(context=context)

            # Обработка FloodWaitError
            except errors.FloodWaitError as exc:
                # Логгируем и ждем указанное время
                self.logger.info(
                    f'{log_prefix} 🟡 got a FloodWaitError, sleeping for '
                    f'{exc.seconds} seconds'
                )
                await asyncio.sleep(exc.seconds)

                # Рекурсивно перевызываем декорированный метод
                self.logger.info(
                    f'{log_prefix} is waking up '
                    'after FloodWaitError and re-calling itself.'
                )
                return await getattr(self, method.__name__)(*args, **kwargs)

            except Exception as exc:
                self._log_exception(
                    exc,
                    log_prefix=f'{log_prefix} 🔸',
                    propagate=context.propagate_exc.get()
                )

        return async_wrapper

    @abstractmethod
    def _is_blocked_by_peer(self):
        """Abstract UserIsBlockedError handler."""
        pass
