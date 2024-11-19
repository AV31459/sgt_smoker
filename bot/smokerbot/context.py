from contextvars import ContextVar, copy_context, Token
from types import FunctionType

from telethon import events, types
from telethon.custom import Message
from telethon.events.common import EventCommon

# NB: contextvars should be created at the top module level
# and never in closures:
# https://docs.python.org/3/library/contextvars.html#context-variables

# Handler method call scope
scope: ContextVar[str] = ContextVar('scope', default='')
method_name: ContextVar[str] = ContextVar('method_name', default='')
method_args: ContextVar[list] = ContextVar('method_args', default=[])
method_kwargs: ContextVar[dict] = ContextVar('method_kwargs', default={})
propagate_exc: ContextVar[bool | None] = (
    ContextVar('propagate_exc', default=None)
)

# Event being processed, if any
event: ContextVar[EventCommon | None] = ContextVar('event', default=None)

# telethon.tl.custom.message.Message, if any
msg: ContextVar[Message | None] = ContextVar('msg', default=None)
msg_id: ContextVar[int | None] = ContextVar('msg_id', default=None)

# from telethon.tl.custom.chatgetter.ChatGetter
chat_id: ContextVar[int | None] = (
    # in practice should always be present in event
    ContextVar('chat_id', default=None)
)
chat: ContextVar[types.User | types.Chat | types.Channel | None] = (
    # might be missing in event
    ContextVar('chat', default=None)
)

# from telethon.tl.custom.sendergetter.SenderGetter
sender_id: ContextVar[int | None] = (
    # in practice should always be present in event
    ContextVar('sender_id', default=None)
)
sender: ContextVar[types.User | types.Channel | None] = (
    # might be missing in event
    ContextVar('sender', default=None)
)

# CallbackQuery
query: ContextVar[types.UpdateBotCallbackQuery | None] = (
    ContextVar('query', default=None)
)
query_id: ContextVar[int | None] = ContextVar('query_id', default=None)
query_data: ContextVar[bytes | None] = ContextVar('query_data', default=None)


def print_vars(prefix='', names=()):
    """Debug only!"""
    ctx = copy_context()
    print(
        f'[{prefix}] vars in context:',
        {k.name: v for k, v in ctx.items() if not names or k.name in names}
    )


def clear_and_set_contextvars(
        scope_val: str,
        event_val: EventCommon | None = None,
        propagate_exc_val: bool | None = None
):
    """Clear all contextvars and set new ones based on given args."""

    # Сбрасываем все значения контекстных переменннх
    for var_name in (
        var.name for var in copy_context().keys() if var.name in globals()
    ):
        globals()[var_name].set(None)

    # Устанавливаем контекст обработки события telethon, при наличии
    if isinstance(event_val, EventCommon):

        # Обработка общих аттрибутов событий telethon event
        # https://docs.telethon.dev/en/stable/quick-references/events-reference.html#events-reference
        for var_name in ('chat_id', 'chat', 'sender_id', 'sender'):
            globals()[var_name].set(getattr(event_val, var_name, None))

        # Для событий типа NewMessage, MessageEdited
        if (
            hasattr(event_val, 'message')
            and isinstance(event_val.message, Message)
        ):
            msg.set(event_val.message)
            msg_id.set(event_val.message.id)

        # Для событий типа CallbackQuery
        if isinstance(event_val, events.CallbackQuery):
            query_id.set(event_val.id)
            msg_id.set(event_val.message_id)
            query_data.set(event_val.data)

    # Устанавливаем значения scope, method_{...}, event, propagate_exc
    if chat_id.get():
        scope.set(f'{scope_val} {build_chat_at_id_string()}:')
    else:
        scope.set(f'[{scope_val}] :')
    event.set(event_val)
    propagate_exc.set(propagate_exc_val)


def set_method_and_modify_scope(
    method: FunctionType,
    args: list,
    kwargs: dict
) -> tuple[Token]:
    """Set new `method_{...}` contextvars, modify `scope` and return tokens."""

    return (
        scope.set(
            f'{scope.get()} {current_method_name}():'
            if (current_method_name := method_name.get())
            else f'{scope.get()}'
        ),
        method_name.set(method.__name__),
        method_args.set(args),
        method_kwargs.set(kwargs),
    )


def reset_method_and_modified_scope(
    scope_token: Token,
    method_name_token: Token,
    method_args_token: Token,
    method_kwargs_token: Token
):
    """Resets values set by `set_method_and_modify_scope`."""

    scope.reset(scope_token)
    method_name.reset(method_name_token)
    method_args.reset(method_args_token)
    method_kwargs.reset(method_kwargs_token)


def build_chat_at_id_string() -> str:
    """Get context-based `[ chat_id @ msg_id ]` string if any."""

    return (f'[ {chat_id.get()} @ {msg_id.get()} ]' if chat_id.get() else '')


def build_log_prefix(call_info: bool = True) -> str:
    """Builds full log prefix string based on current context.

    Built prefix looks like:
    `scope : method() call with args=[...], kwargs={...}:`,
    where values are obtained from current context.
    """

    return (
        f'{scope.get()}'
        + (f' {method_name.get()}() call with args={method_args.get()}, '
           f'kwargs={method_kwargs.get()}:' if call_info else '')
    )


def build_scope_prefix() -> str:
    """Shortcut for `build_log_prefix(call_info=False)."""

    return build_log_prefix(call_info=False)
