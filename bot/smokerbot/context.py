from contextvars import ContextVar, copy_context

from telethon import types
from telethon.custom import Message
from telethon.events.common import EventCommon

# NB: contextvars should be created at the top module level
# and never in closures:
# https://docs.python.org/3/library/contextvars.html#context-variables

# Handler method call scope
scope: ContextVar[str | None] = ContextVar('scope', default=None)
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
query_msg_id: ContextVar[int | None] = ContextVar('query_msg_id', default=None)
query_data: ContextVar[bytes | None] = ContextVar('query_data', default=None)


def print_vars(prefix=''):
    """Debug only"""
    print(f'[{prefix}]\n Printing vars set in context:')
    ctx = copy_context()
    print(list(ctx.items()))


def build_context(
        scope_val: str,
        event_val: EventCommon | None = None,
        propagate_exc_val: bool | None = None
):
    """Установить значения контекстных переменных."""

    # Сбрасываем значения контекстных переменннх (just in case)
    for var_name in (var.name for var in copy_context().keys()):
        globals()[var_name].set(None)

    # Устанавливаем новые значения
    scope.set(scope_val)
    event.set(event_val)
    propagate_exc.set(propagate_exc_val)
