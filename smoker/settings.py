import logging

LOG_CONFIG = {
    'version': 1,
    'formatters': {
        'basic': {
            'format': '%(asctime)s - [%(levelname)s] - %(name)s.'
            '%(funcName)s:%(lineno)d - %(message)s',
        },
    },
    'handlers': {
        'stream_handler': {
            'class': 'logging.StreamHandler',
            'formatter': 'basic',
        },
        'file_handler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'smoker.log',
            'maxBytes': 5_000_000,
            'backupCount': 5,
            'encoding': 'utf-8',
            'formatter': 'basic',
        },
    },
    'loggers': {
        'httpx': {
            'level': logging.WARNING
        },
        'apscheduler': {
            'level': logging.WARNING
        }
    },
    'root': {
        'level': logging.INFO,
        'handlers': ['stream_handler', 'file_handler'],
    },
    'disable_existing_loggers': False,
}

USERDATA_FILEPATH = 'userdata'

BOT_LOG_LEVEL = logging.DEBUG
