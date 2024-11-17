from .basehandler import BaseHandler


class ClientMixin:
    """Методы для работы с Телеграм через `self.client`."""

    @BaseHandler.handle_exceptions
    async def _get_messages(self, *args, **kwargs):
        """Обертка-обработчик исключений над `self.client.get_messages(...)`"""

        return await self.client.get_messages(*args, **kwargs)

    @BaseHandler.handle_exceptions
    async def _get_entity(self, *args, **kwargs):
        """Обертка-обработчик исключений над `self.client.get_entity(...)`"""

        return await self.client.get_entity(*args, **kwargs)

    @BaseHandler.handle_exceptions
    async def _send_message(self, *args,  **kwargs):
        """Обертка-обработчик исключений над `self.client.send_message(...)`"""

        return await self.client.send_message(*args, **kwargs)

    @BaseHandler.handle_exceptions
    async def _client_call(self, *args,  **kwargs):
        """Обертка-обработчик исключений над `self.client(...)`"""

        return await self.client(*args, **kwargs)

    @BaseHandler.handle_exceptions
    async def _send_read_acknowledge(self, *args, **kwargs):
        """Обертка-обработчик над `.client.send_read_acknowledge(...)`"""

        return await self.client.send_read_acknowledge(*args, **kwargs)
