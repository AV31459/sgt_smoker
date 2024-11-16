import asyncio
import functools
from abc import ABC, abstractmethod
from logging import Logger
from contextvars import copy_context

from telethon import TelegramClient, errors
from telethon.events.common import EventCommon

from .core import Context
from . import context


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
    def build_context(
        scope: str,
        event_handling: bool = False,
        propagate_exc: bool = False
    ):
        """Декоратор для создания отдельного контекста выполнения метода.

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

        def decorator(method):

            @functools.wraps(method)
            def wrapper(self: BaseHandler, *args, **kwargs):

                if (
                    event_handling
                    and not (
                        len(args) == 1 and isinstance(args[0], EventCommon)
                    )
                ):
                    self._log_exception(
                        ValueError(
                            f'a {method.__name__}() method was decorated as '
                            '\'event_handling\', so it must be callled with '
                            'telethone \'event\' as a single positional '
                            'argument.'
                        ),
                        log_prefix='context build error:',
                        propagate=True
                    )

                ctx = copy_context()
                ctx.run(
                    context.build_context,
                    scope_val=scope,
                    event_val=(args[0] if event_handling else None),
                    propagate_exc_val=propagate_exc
                )

                prefix = (
                    f'exp_build_context wrapper, scope={scope}, '
                    f'method={method.__name__}, after setting scope:'
                )
                context.print_vars(prefix)

                return ctx.run(method, self, *args, **kwargs)

            return wrapper

        return decorator

    @staticmethod
    def _build_context(method):
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

        *experimental* При получении FloodError засыпает на указанное число
        секунд и рекурсивно перевызывает исходный (декорированный) метод.

        Декорируемый метод должен получать ***обязательный именованный***
        ***параметр 'context'***, содержащий следующие аттрибуты:

            - `log_prefix`: str - префикс сообщения об ошибке
            - `propagate_exc`: bool - перевызывать ли исключение после
            логгирования
        """

        @functools.wraps(method)
        def wrapper(self: BaseHandler, *args, **kwargs):

            call_info_string = (
                f' {method.__name__}() call with args={args}, '
                f'kwargs={kwargs}:'
            )

            # Проверка наличия контекста
            if not (
                (context := kwargs.get('context'))
                and isinstance(context, Context)
            ):
                self._log_exception(
                    ValueError('method must be called with valid \'context\' '
                               'argument in kwargs.'),
                    log_prefix=call_info_string,
                    propagate=True
                )

            log_prefix = context.log_prefix + call_info_string
            propagate_exc = context.propagate_exc

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
