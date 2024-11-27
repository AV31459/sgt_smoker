from telethon import types
from telethon.tl.functions.messages import SendReactionRequest

from . import context
from .basehandler import BaseHandler
from .helpers import get_emoji_reaction_from_msg


class ClientMixin:
    """Методы для работы с Телеграм через `self.client`."""

    manage_context = BaseHandler.manage_context

    @manage_context
    async def _get_messages(self, *args, **kwargs):
        """Контекстная обертка над `self.client.get_messages(...)`"""

        return await self.client.get_messages(*args, **kwargs)

    @manage_context
    async def _get_entity(self, *args, **kwargs):
        """Контекстная обертка над `self.client.get_entity(...)`"""

        return await self.client.get_entity(*args, **kwargs)

    @manage_context
    async def _send_message(self, *args,  **kwargs):
        """Контекстная обертка над `self.client.send_message(...)`"""

        return await self.client.send_message(*args, **kwargs)

    @manage_context
    async def _edit_message(self, *args,  **kwargs):
        """Контекстная обертка над `self.client.edit_message(...)`"""

        return await self.client.edit_message(*args, **kwargs)

    @manage_context
    async def _delete_messages(self, *args,  **kwargs):
        """Контекстная обертка над `self.client.delete_messages(...)`"""

        return await self.client.delete_messages(*args, **kwargs)

    @manage_context
    async def _client_call(self, *args,  **kwargs):
        """Контекстная обертка над `self.client(...)`"""

        return await self.client(*args, **kwargs)

    @manage_context
    async def _send_read_acknowledge(self, *args, **kwargs):
        """Контекстная обертка над `.client.send_read_acknowledge(...)`"""

        return await self.client.send_read_acknowledge(*args, **kwargs)

    @manage_context
    async def _set_reaction_emoji(self, emoji: str | None):
        """Установить реакцию для сообщения в контексте."""

        if (
            not (msg := context.msg.get())  # контекст без сообщения
            or (emoji == get_emoji_reaction_from_msg(msg, self._self_id))
        ):
            return

        await self._client_call(
            SendReactionRequest(
                peer=msg.peer_id,
                msg_id=msg.id,
                add_to_recent=True,
                reaction=[types.ReactionEmoji(emoji) if emoji
                          else types.ReactionEmpty()]
            )
        )
