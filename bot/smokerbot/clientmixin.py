from .basehandler import BaseHandler


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
    async def _client_call(self, *args,  **kwargs):
        """Контекстная обертка над `self.client(...)`"""

        return await self.client(*args, **kwargs)

    @manage_context
    async def _send_read_acknowledge(self, *args, **kwargs):
        """Контекстная обертка над `.client.send_read_acknowledge(...)`"""

        return await self.client.send_read_acknowledge(*args, **kwargs)
