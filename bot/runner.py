# import asyncio
import logging
import os
from logging.config import dictConfig
from pathlib import Path

import settings
from dotenv import load_dotenv
from smokerbot import SmokerBotHandler
from telethon import TelegramClient, events


def bot_runner():
    """Запуск бота."""

    load_dotenv()

    # Настраиваем логгер
    logger = logging.getLogger('smokerbot')
    dictConfig(settings.LOG_CONFIG)
    logger.setLevel(os.getenv('APP_LOG_LEVEL', 'INFO'))
    logger.info('Smokerbot is being started...')

    # Коннектим Телеграм клиент
    client = TelegramClient(
        Path(os.getenv('DATA_PATH')) / 'smokerbot.session',
        os.getenv('CLIENT_API_ID'),
        os.getenv('CLIENT_API_HASH'),
        app_version=os.getenv('CLIENT_APP_VERSION'),
        system_version=os.getenv('CLIENT_SYSTEM_VERSION'),
        connection_retries=int(os.getenv('CLIENT_CONNECTION_RETRIES'))
    ).start(bot_token=os.getenv('BOT_TOKEN'))

    # Настройка авто-обработки FloodWaitError модулем Telethon
    if threshold := os.getenv('CLIENT_FLOOD_SLEEP_THRESHOLD'):
        client.flood_sleep_threshold = int(threshold)

    # Создаем основной bot handler
    handler = SmokerBotHandler(
        client,
        logger,
        data_path=Path(os.getenv('DATA_PATH')),
        admin_ids=[int(os.getenv('ADMIN_USER_ID'))],
        persistence_interval=int(os.getenv('PERSISTENCE_INTERVAL', 600))
    )

    # Регистрируем обработчики событий
    client.add_event_handler(
        handler.on_new_message,
        events.NewMessage(incoming=True, func=handler.filter_event)
    )
    client.add_event_handler(
        handler.on_callback_query,
        events.CallbackQuery(func=handler.filter_event)
    )

    # Запускаем asyncio loop
    with client:
        logger.info('Running main asyncio loop until disconnected')

        # client.run_until_disconnected() is a simplier alternative, but
        # in such case SIGINT or KeyboardInterrupt can not be handled properly
        try:
            client.loop.run_until_complete(client.disconnected)
        except KeyboardInterrupt as exc:
            logger.info(exc.__class__.__name__)
        except BaseException as exc:
            logger.error(
                'Unhandled exception in main loop: 🟥 '
                f'{exc.__class__.__name__}: {exc}', exc_info=True
            )
        finally:
            handler.shutdown()


if __name__ == '__main__':
    bot_runner()