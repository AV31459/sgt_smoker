from contextvars import ContextVar, copy_context
from typing import Callable

from telethon import types, events
from telethon.custom import Message
from telethon.events.common import EventCommon


# NB: contextvars should be created at the top module level
# and never in closures:
# https://docs.python.org/3/library/contextvars.html#context-variables

# Handler method call scope
scope: ContextVar[str | None] = ContextVar('scope', default=None)
sub_scope: ContextVar[str | None] = ContextVar('sub_scope', default=None)
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


def print_vars(prefix=''):
    """Debug only"""
    ctx = copy_context()
    print(f'[{prefix}] vars set in context:', 
          {k.name: v for k, v in ctx.items()})


def build_context(
        scope_val: str,
        event_val: EventCommon | None = None,
        propagate_exc_val: bool | None = None
):
    """Set context variable values besed on given arguments."""

    # Сбрасываем значения контекстных переменннх (just in case)
    for var_name in (
        var.name for var in copy_context().keys() if var.name in globals()
    ):
        globals()[var_name].set(None)

    # Устанавливаем значения переменных, передаваемых явным образом
    scope.set(scope_val)
    event.set(event_val)
    propagate_exc.set(propagate_exc_val)

    if not isinstance(event_val, EventCommon):
        return

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


def build_log_prefix(method: Callable = None, args=[], kwargs={}) -> str:
    """Builds log prefix string based on current context.

    Built prefix looks like:
    `scope [chat_id @ msg_id] : method() call with args=[...], kwargs={...}:`,
    where:

    - `scope`, `chat_id`, `msg_id` - values are obtained from current context,
    - `method`, `args`, `kwargs` - optional arguments.
    """

    return (
        str(scope.get())
        + (f' [{chat_id.get()} @ {msg_id.get()}] :' if chat_id.get() else ' :')
        + (f' {sub_scope.get()} :' if sub_scope.get() else '')
        + (
            f' {method.__name__}() call with args={args}, kwargs={kwargs} :'
            if method else ''
        )
    )
