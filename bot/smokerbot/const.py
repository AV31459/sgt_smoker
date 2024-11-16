# from telethon import types
from telethon.types import BotCommand

BOT_COMMANDS_LANG_CODE = 'ru'

BOT_COMMANDS_DEFAULT = [
    BotCommand(command='run', description='🟢 Запуск таймера'),
    BotCommand(command='smoke', description='🚬 Выкурить сигарету'),
    BotCommand(command='stop', description='🔴 Останов таймера'),
    BotCommand(command='status', description='ℹ️ Текущий статус'),
    BotCommand(command='settings', description='⚙️ Настройки'),
    BotCommand(command='help', description='🆘 Помощь'),
]
