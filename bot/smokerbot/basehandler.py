import asyncio
import functools
from abc import ABC, abstractmethod
from contextvars import Context
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
    def new_context(
        task_name: str = '',
        event_handling: bool = False,
        propagate_exc: bool = False
    ):
        """Декоратор для создания нового контекста выполнения метода.

        Параметры:
            - `task_name` - имя создаваемой задачи, если параметр не
            передается (по умолчанию пустая строка) используется имя
            декорируемого метода
            - `event_handling` - декорируемый метод является обработчиком
            событий telethon, т.е. получает единственный аргумент типа
            `telethon.events.common.EventCommon`, по умолчанию False
            - `propagate_exc` - перевызовать необрабатываемые исключения после
            логгирования, по умолчанию False

        Может быть использован как синхронными, так и ассинхронными методами.

        NB: при использовании нескольких декораторов, должен быть самым
        последним (верхний уровень).
        """

        def build_context_obj(method, self, args, kwargs) -> Context:
            """Common logic for both sync and async decorators.

            Returns new `context_obj: Context`.
            """

            if (
                event_handling
                and not (len(args) == 1 and isinstance(args[0], EventCommon))
            ):
                self._log_exception(
                    ValueError(
                        f'{context.get_log_prefix()} '
                        'Method was decorated as \'event_handling\', so it '
                        'must be called with single positional argument '
                        'of telethone \'Event\' type'
                    ),
                    log_prefix='context build error:',
                    propagate=True
                )

            ctx = Context()
            ctx.run(
                context.init_contextvars,
                task_name_val=task_name or method.__name__,
                event_val=(args[0] if event_handling else None),
                propagate_exc_val=propagate_exc
            )
            return ctx

        def decorator(method):

            if not asyncio.iscoroutinefunction(method):
                # Синхронный декоратор
                @functools.wraps(method)
                def sync_new_context_wrapper(
                    self: BaseHandler, *args, **kwargs
                ):

                    return (
                        build_context_obj(method, self, args, kwargs)
                        .run(method, self, *args, **kwargs)
                    )

                return sync_new_context_wrapper

            # Асинхронный декоратор
            @functools.wraps(method)
            async def async_new_context_wrapper(
                self: BaseHandler, *args, **kwargs
            ):

                return self._loop.create_task(
                    method(self, *args, **kwargs),
                    context=build_context_obj(method, self, args, kwargs)
                )

            return async_new_context_wrapper

        return decorator

    @staticmethod
    def manage_context(method):
        """Декоратор для обновления контекста и обработки исключений.

        Перед вызовом метода устанавливает значения контекстных переменных
        `call_chain`, `method_name`, `method_args`, `method_kwargs`.
        Восстанавливает исходные значения после завершения метода.

        Использует следующие переменные контекста:
            - `task_name`, `call_chain`, `method_{...}` - для формирования
            префикса логгирования ошибки
            - `propagate_exc`: bool - перевызывать ли необрабатываемое
            исключение после логгирования

        Перехватывает и логгирует все  'non-exit' исключения. Отдельно
        обрабатывает следющие:

            - `telethon.errors.UserIsBlockedError` - запуск обработчика
            _on_blocked_by_peer(),
            - `MessageNotModifiedError` - игнорируется,
            - `telethon.errors.FloodWaitError` - *experimental* засыпает на
            указанное число секунд и рекурсивно перевызывает исходный
            (декорированный) метод.

        Может быть использован как синхронными, так и ассинхронными методами.
        """

        if not asyncio.iscoroutinefunction(method):

            # Sync decorator
            @functools.wraps(method)
            def sync_manage_context_wrapper(
                self: BaseHandler, *args, **kwargs
            ):

                try:
                    tokens = context.enter_method(method, args, kwargs)
                    return method(self, *args, **kwargs)

                except Exception as exc:
                    self._log_exception(
                        exc,
                        log_prefix=f'{context.get_log_prefix()} 🔸',
                        propagate=context.propagate_exc.get()
                    )

                finally:
                    context.exit_method(*tokens)

            return sync_manage_context_wrapper

        # Async decorator
        @functools.wraps(method)
        async def async_manage_context_wrapper(
            self: BaseHandler, *args, **kwargs
        ):

            try:
                tokens = context.enter_method(method, args, kwargs)
                return await method(self, *args, **kwargs)

            # Обработка UserIsBlockedError
            except errors.UserIsBlockedError:
                await self._on_blocked_by_peer()

            # Обработка MessageNotModifiedError
            except errors.MessageNotModifiedError:
                pass

            # Обработка FloodWaitError
            except errors.FloodWaitError as exc:
                # Логгируем и ждем указанное время
                self.logger.info(
                    f'{context.get_log_prefix()} 🟡 got a FloodWaitError, '
                    f'sleeping for {exc.seconds} seconds'
                )
                await asyncio.sleep(exc.seconds)

                # Рекурсивно перевызываем декорированный метод
                self.logger.info(
                    f'{context.get_log_prefix()} is waking up '
                    'after FloodWaitError and re-calling itself.'
                )
                return await getattr(self, method.__name__)(*args, **kwargs)

            except Exception as exc:
                self._log_exception(
                    exc,
                    log_prefix=f'{context.get_log_prefix()} 🔸',
                    propagate=context.propagate_exc.get()
                )

            finally:
                context.exit_method(*tokens)

        return async_manage_context_wrapper

    @abstractmethod
    async def _on_blocked_by_peer(self):
        """Abstract UserIsBlockedError handler."""
        pass
