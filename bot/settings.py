import logging

LOG_CONFIG = {
    'version': 1,
    'formatters': {
        'basic': {
            'format': '%(levelname)s:\t%(name)s:  %(asctime)s : %(message)s',
        },
    },
    'handlers': {
        'stream_handler': {
            'class': 'logging.StreamHandler',
            'formatter': 'basic',
        },
        'file_handler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/smoker.log',
            'maxBytes': 5_000_000,
            'backupCount': 5,
            'encoding': 'utf-8',
            'formatter': 'basic',
        },
    },
    'loggers': {
        'telethon': {
            'level': logging.WARN
        },
    },
    'root': {
        'level': logging.INFO,
        'handlers': ['stream_handler', 'file_handler'],
    },
    'disable_existing_loggers': False,
}
