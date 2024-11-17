from dataclasses import dataclass

from telethon import types
from telethon.tl.custom.message import Message
from telethon.events.common import EventCommon


@dataclass
class Context:
    """Класс контекста обработки события.

    Аттрибуты устанавливаются на основе полученного события (Event), по
    возмможности 'безопасным' способом, т.е. без потенциальных дополнительных
    обращений к API.

    Также содержит атрибуты внутреннего контекста `log_prefix` и
    `propagate_exc` для логгирования и обработки исключений  сооответвующим
    декоратором.
    """

    # from telethon.tl.custom.chatgetter.ChatGetter
    chat_id: int = None    # in practice should always be set
    chat: types.User | types.Chat | types.Channel | None = None

    # from telethon.tl.custom.sendergetter.SenderGetter (NewMessage)
    sender_id: int = None   # in practice should always be set
    sender: types.User | types.Channel | None = None

    # telethon.tl.custom.message.Message
    msg: Message | None = None
    msg_id: int | None = None

    # Original query
    query: types.UpdateBotCallbackQuery | None = None
    query_id: int | None = None
    query_msg_id: int | None = None
    query_data: bytes | None = None

    # internal handler context
    _log_prefix: str | None = None
    propagate_exc: bool = False

    # original event if any
    event: EventCommon | None = None

    @staticmethod
    def build_from_event(event: EventCommon):
        """Create `Context` instance based on given `Event`."""

        return Context(
            chat_id=event.chat_id,
            chat=event.chat,

            sender_id=event.sender_id,
            sender=event.sender,

            msg=(event.message if hasattr(event, 'message') else None),
            msg_id=(event.message.id if hasattr(event, 'message')
                    else event.message_id if hasattr(event, 'message_id')
                    else None),

            query=(event.query if hasattr(event, 'query') else None),
            query_id=(
                event.id if (hasattr(event, 'query') and hasattr(event, 'id'))
                else None
            ),
            query_data=(event.sender if hasattr(event, 'data') else None),
            event=event
        )

    def get_chat_at_id_string(self) -> str:
        """Get `[ chat_id @ msg_id ]:` string based on data available."""

        return f'[ {self.chat_id} @ {self.msg_id} ]:'

    @property
    def log_prefix(self):
        """If not yet set explicitly return default `[ chat_id @ msg_id ]`"""
        return (self._log_prefix if self._log_prefix
                else self.get_chat_at_id_string())

    @log_prefix.setter
    def log_prefix(self, value):
        self._log_prefix = value


def trunc(message: str | None, n: int = 40):
    """Truncates long string to *n* symbols adding trailng [...] if needed."""

    if isinstance(message, str):
        return message[:n] + ('[...]' if len(message) > n else '')

    return message


def get_chat_at_id_string(msg: Message) -> str:
    """Get *'[ chat_id @ id ]:'* string for `telethone.Message`."""

    return f'[ {msg.chat_id} @ {msg.id} ]:'


def get_message_info_string(msg: Message) -> str:
    """Get brief attributes string for `telethone.Message`."""

    return (
        f'chat_id={msg.chat_id}, msg.id={msg.id}, '
        f'sender_id={msg.sender_id}, peer_id={msg.peer_id}, '
        f'from_id={msg.from_id}, '
        f'fwd_from.from_id={msg.fwd_from.from_id if msg.fwd_from else None}, '
        f'action={msg.action}, message="{trunc(msg.message)}"'
    )
