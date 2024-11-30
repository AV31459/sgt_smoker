from contextvars import ContextVar, copy_context, Token
from types import FunctionType

from telethon import events, types
from telethon.custom import Message
from telethon.events.common import EventCommon

# NB: contextvars should be created at the top module level
# and never in closures:
# https://docs.python.org/3/library/contextvars.html#context-variables

# Handler method call scope
task_name: ContextVar[str] = ContextVar('task_name', default='')
call_chain: ContextVar[str] = ContextVar('call_chain', default='')
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


def init_contextvars(
        task_name_val: str,
        event_val: EventCommon | None = None,
        propagate_exc_val: bool | None = None,
        sender_id_val: int | None = None,
        sender_val: types.User | None = None
):
    """Set contextvars based on given args."""

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
        if isinstance(event_val, events.CallbackQuery.Event):
            query_id.set(event_val.id)
            msg_id.set(event_val.message_id)
            query_data.set(event_val.data)

    # Устанавливаем значения task_name, event, propagate_exc
    task_name.set(task_name_val)
    event.set(event_val)
    propagate_exc.set(propagate_exc_val)

    # Если значения для 'sender_id', 'sender' были переданы в явном виде -
    # то устанавливаем их из аргументов
    if sender_id_val:
        sender_id.set(sender_id_val)
    if sender_val:
        sender.set(sender_val)


def enter_method(
    method: FunctionType,
    args: list,
    kwargs: dict
) -> tuple[Token]:
    """Set `method_{...}` contextvars, modify `call_chain`, return tokens."""

    return (
        call_chain.set(
            f'{call_chain.get()} {current_method_name}():'
            if (current_method_name := method_name.get())
            else f'{call_chain.get()}'
        ),
        method_name.set(method.__name__),
        method_args.set(args),
        method_kwargs.set(kwargs),
    )


def exit_method(
    call_chain_token: Token,
    method_name_token: Token,
    method_args_token: Token,
    method_kwargs_token: Token
):
    """Resets values set by `enter_method()`."""

    call_chain.reset(call_chain_token)
    method_name.reset(method_name_token)
    method_args.reset(method_args_token)
    method_kwargs.reset(method_kwargs_token)


def get_log_prefix() -> str:
    """Builds full log prefix string based on current context.

    Built prefix looks like:
    `task_name : call_chain : method() call with args=[...], kwargs={...}:`,
    where values are obtained from current context.
    """

    return (
        f'{get_task_prefix()}'
        + (f' {call_chain.get()}' if call_chain.get() else '')
        + (f' {method_name.get()}() call with args={method_args.get()}, '
           f'kwargs={method_kwargs.get()}:')
    )


def get_task_prefix() -> str:
    """Builds task name prefix string based on current context.

    Built prefix looks like: `task name [ <chat_id> @ <msg_id> ]:`
    """

    return (
        (
            chat.get()
            and (
                f'{task_name.get()} '
                f'[ {chat.get().username} @ {msg_id.get()} ]:'
            )
        )
        or (
            chat_id.get()
            and f'{task_name.get()} [ {chat_id.get()} @ {msg_id.get()} ]:'
        )
        or f'[ {task_name.get()} ]:'
    )
