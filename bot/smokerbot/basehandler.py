import asyncio
import functools
from abc import ABC, abstractmethod
from contextvars import Context, copy_context
from logging import Logger
from contextlib import contextmanager

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
        scope: str = '',
        event_handling: bool = False,
        propagate_exc: bool = False
    ):
        """Декоратор для создания нового контекста выполнения метода.

        Параметры:
            - `scope` - область (имя) создаваемого контекста, если параметр не
            передается (по умолчанию пустая строка) используется имя метода
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
                        f'{context.build_log_prefix()} '
                        'Method was decorated as \'event_handling\', so it '
                        'must be called with single positional argument '
                        'of telethone \'Event\' type'
                    ),
                    log_prefix='context build error:',
                    propagate=True
                )

            ctx = copy_context()
            ctx.run(
                context.clear_and_set_contextvars,
                scope_val=scope or method.__name__,
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
        `scope`, `method_name`, `method_args`, `method_kwargs`.
        Восстанавливает исходные значения после завершения метода.

        Перехватывает и логгирует все исключения. Отдельно обрабатывает
        следющие исключения:
            - `errors.UserIsBlockedError`
            - `errors.FloodWaitError`

        *experimental* При получении FloodError засыпает на указанное число
        секунд и рекурсивно перевызывает исходный (декорированный) метод.

        Использует следующие переменные контекста:

            - `scope`, `method_{name, args, kwargs}` - для формирования
            префикса логгирования ошибки
            - `propagate_exc`: bool - перевызывать ли необрабатываемое
            исключение после логгирования

        Может быть использован как синхронными, так и ассинхронными методами.
        """

        @contextmanager
        def context_updater(method, args, kwargs):
            """Update/reset relevant contextvars."""

            scope_token = context.scope.set(
                f'{context.scope.get()} {calling_method_name}():'
                if (calling_method_name := context.method_name.get())
                else f'{context.scope.get()}'
            )
            method_name_token = context.method_name.set(method.__name__)
            method_args_token = context.method_args.set(args)
            method_kwargs_token = context.method_kwargs.set(kwargs)

            yield

            context.scope.reset(scope_token)
            context.method_name.reset(method_name_token)
            context.method_args.reset(method_args_token)
            context.method_kwargs.reset(method_kwargs_token)

        if not asyncio.iscoroutinefunction(method):

            # Синхронный декоратор
            @functools.wraps(method)
            def sync_manage_context_wrapper(
                self: BaseHandler, *args, **kwargs
            ):

                try:
                    with context_updater(method, args, kwargs):
                        return method(self, *args, **kwargs)
                except Exception as exc:
                    self._log_exception(
                        exc,
                        log_prefix=f'{context.build_log_prefix()} 🔸',
                        propagate=context.propagate_exc.get()
                    )

            return sync_manage_context_wrapper

        # Асинхронный декоратор
        @functools.wraps(method)
        async def async_manage_context_wrapper(
            self: BaseHandler, *args, **kwargs
        ):

            log_prefix = context.build_log_prefix()

            try:
                with context_updater(method, args, kwargs):
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

        return async_manage_context_wrapper

    @abstractmethod
    def _is_blocked_by_peer(self):
        """Abstract UserIsBlockedError handler."""
        pass
