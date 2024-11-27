# from telethon import types
import re

from telethon.types import BotCommand

USER_DATA_DEFAULT = {
    'is_active_user': True,

    'is_running': False,
    'is_timer': False,

    'mode': 'auto',
    'interval': 60,
    'initial_sig': 1,
    'tz_offset': 3,

    'ran_at': None,
    'sig_available': 0,
    'sig_smoked': 0,
    'timer_start': None,
    'timer_end': None
}

BOT_COMMAND_NAME_RE_DICT = {
    # <каноническое имя>: <cкомпилированный regex>
    'start': re.compile(
        r'(?i)^/(?P<name>start)[\s]*$'
    ),
    'help': re.compile(
        r'(?i)^/(?P<name>help)[\s]*$'
    ),
    'settings': re.compile(
        r'(?i)^/(?P<name>settings)[\s]*$'
    ),
    'setmode': re.compile(
        r'^/(?i:(?P<name>setmode))'
        r'([\s]+(?P<mode>auto|manual))?[\s]*$'
    ),
    'setinterval': re.compile(
        r'^/(?i:(?P<name>setinterval))'
        r'([\s]+(?P<interval>[1-7]?[0-9]{1,2}))?[\s]*$'
    ),
    'setinitial': re.compile(
        r'^/(?i:(?P<name>setinitial))'
        r'([\s]+(?P<initial_sig>[0-3]))?[\s]*$'
    ),
    'settz': re.compile(
        r'^/(?i:(?P<name>settz))'
        r'([\s]+(?P<tz_offset>[+-]?(1[0-2]|\d)))?[\s]*$'
    ),
    'status': re.compile(
        r'(?i)^/(?P<name>status)[\s]*$'
    ),
    'run': re.compile(
        r'(?i)^/(?P<name>run)[\s]*$'
    ),
    'stop': re.compile(
        r'(?i)^/(?P<name>stop)[\s]*$'
    ),
    'smoke': re.compile(
        r'(?i)^/(?P<name>smoke)[\s]*$'
    ),
    # Команда администратора
    'info': re.compile(
        r'(?i)^/(?P<name>info)[\s]*$'
    ),
}

# Имена re-групп, содержащих целочисленные значнеия
BOT_COMMAND_INT_RE_GROUPS = ('interval', 'initial_sig', 'tz_offset',)

BOT_COMMANDS_LANG_CODE = 'ru'

BOT_COMMANDS_DEFAULT = [
    BotCommand(command='run', description='❇ Запуcтить таймер'),
    BotCommand(command='smoke', description='🚬 Выкурить сигарету'),
    BotCommand(command='stop', description='🛑 Остановить таймер'),
    BotCommand(command='status', description='ℹ️ Текущий статус'),
    BotCommand(command='settings', description='⚙️ Настройки'),
    BotCommand(command='help', description='🆘 Помощь'),
    BotCommand(command='setinterval', description='⚙️🔢 Установить интервал'),
    BotCommand(command='setmode', description='⚙️🔠 Режим перезапуска таймера'),
    BotCommand(command='setinitial', description='⚙️🔢 Начальное кол-во '
               'сигарет'),
    BotCommand(command='settz', description='⚙️🔢 Часовой пояс'),
]


# Эмоджи строки, поддерживаемые Telegram API
EMOJI_OK = '👌'
EMOJI_LIKE = '👍'
EMOJI_DISLIKE = '👎'
EMOJI_SHRUG = '🤷\u200d♂'
EMOJI_WRITE = '✍'
EMOGI_HEART = '❤'
EMOGI_YELL = '🤬'
EMOGI_GREEN_CIRCLE = '🟢'
EMOGI_YELLOW_CIRCLE = '🟡'


MSG_START = (
    'Ну здравствуй, {name}! 😐\n\n'
    'Прочти /help и установи себе настройки ⚙️ /settings\n\n'
    '... и помни - я слежу за тобой 🤫'
)

MSG_HELP = (
    'Для управления используй кнопку __**Меню**__ внизу экрана\n\n'

    '__**Команды бота:**__\n\n'

    '❇\t/run - запустить таймер\n\n'

    '🚬\t/smoke -  выкурить сигарету\n\n'

    '🛑\t/stop -  остановить таймер\n\n'

    'ℹ️\t/status - текущий статус бота\n\n'

    '⚙️\t/settings - показать настройки\n\n'

    '🆘\t/help -  показать это сообщение\n\n'

    '__**Установка настроек:**__ \n\n'

    '⚙️🔢\t/setinterval - интервал в минутах между '
    'сигаретами\n[__с клавиатуры ⌨️:__ `/setinterval 60`]\n\n'

    '⚙️🔠\t/setmode - **режим перезапуска** для таймера:\n'
    '\t▫ __**авто**__: таймер перезапускается сразу после окончания '
    'очередного интервала\n[__с клавиатуры ⌨️:__ `/setmode auto`]\n'
    '\t▫ __**вручную**__: таймер перезапускается после сообщения '
    'о выкуренной сигарете\n[__с клавиатуры ⌨️:__ `/setmode manual`]\n\n'

    '⚙️🔢\t/setinitial - начальное кол-во доступных сигарет после '
    'запуска\n[__с клавиатуры ⌨️:__ `/setinitial 1`]\n\n'

    '⚙️🔢\t/settz - часовой пояс\n[__с клавиатуры ⌨️:__ `/settz 3`]'
)

MSG_SETTINGS = (
    '⚙️ **Текущие настройки**:\n'
    '▫ Интревал между 🚬: **{interval}** мин\n'
    '▫ Перезапуск таймера: {mode}\n'
    '▫ Сигарет в начале: **{initial_sig}**\n'
    '▫ Часовой пояс: **UTC{tz_offset:+}**\n\n'
)

MSG_INFO = (
    '🔵 **Статус бота**:\n'
    '▫ Пользователи: **{n_users}**\n'
    '▫ Память: {mem_mb:.0f} Mb\n'
)

STR_MODE_AUTO = '**авто** __(сразу после окончания интервала)__'
STR_MODE_MANUAL = '**вручную** __(после сообщения о выкуренной сигарете)__'

MSG_SETTING_SUCCESS_PREFIX = '🆗 Настройка успешно изменена.\n\n'

INTERVAL_MIN = 1
INTERVAL_MAX = 720

INITIAL_SIG_MIN = 0
INITIAL_SIG_MAX = 3

TZ_OFFSET_MIN = -12
TZ_OFFSET_MAX = 12

SECONDS_IN_MINUTE = 60
SECONDS_IN_HOUR = 3600

MSG_STATUS_RUNNING = (
    'ℹ️ Таймер **запущен** ✔️\n\n'
    'Доступно сигарет:  **{sig_available}** {colored_circle}\n'
    'Следующая 🚬 в {timer_end}\n'
    'Осталось ⏱️  **{time_remaining}**\n\n'
    '__Обновлено {now}__\n'
)

MSG_STATUS_PAUSED = (
    'ℹ️ Таймер **на паузе** ✔️\n\n'
    'Доступно сигарет:  **{sig_available}** {colored_circle}\n\n'
    'Перезапуск после 🚬 /smoke\n\n'
    '__Обновлено {now}__\n'
)

MSG_STATUS_STOPPED = 'ℹ️ Таймер **остановлен** 🛑\n'

MSG_RUN_ALREADY_RUNNING = 'Сервис __**уже**__ запущен ❇'

MSG_ERROR_CHECK_SETTINGS = (
    '⚠️ Внутренняя ошибка, таймер остановлен\nПроверьте настройки!'
)

MSG_NEW_CIG_AVALABLE = (
    'Доступна **+1** 🚬 !\n'
    'Всего доступно: **{sig_available}**'
)

MSG_STOP_SMOKED_CIGS = 'Всего выкурено **{sig_smoked}** сигарет'

MSG_SMOKE_NEGATIVE_STOPPED = 'Отказать! 🤬\nСначала запусти таймер: /run ⏱️'

MSG_SMOKE_NEGATIVE_NO_SIG_AVAILABLE = (
    'Отказать! 🤬\nВремя не подошло, доступных 🚬 нет!'
)

MSG_SMOKE_AFFIRMATIVE = '🚬 выкурена 🆗\n'

CALLBACK_BTN_TEXT_UPDATE = 'Обновить'
CALLBACK_BTN_TEXT_MINUS_10 = '-10'
CALLBACK_BTN_TEXT_MINUS_1 = '-1'
CALLBACK_BTN_TEXT_PLUS_1 = '+1'
CALLBACK_BTN_TEXT_PLUS_10 = '+10'
CALLBACK_BTN_TEXT_SET = 'Установить'
CALLBACK_BTN_TEXT_AUTO = 'Auto'
CALLBACK_BTN_TEXT_MANUAL = 'Manual'

CALLBACK_COMMAND_STATUS_UPDATE = 'status_update'
CALLBACK_COMMAND_SETINTERVAL = 'setinterval {action} {interval}'
CALLBACK_COMMAND_SETMODE = 'setmode {action} {mode}'
CALLBACK_COMMAND_SETINITIAL = 'setinitial {action} {initial_sig}'
CALLBACK_COMMAND_SETTZ = 'settz {action} {tz_offset}'

BOT_CALLBACK_COMMANDS_RE = (
    # <cкомпилированные regex>
    re.compile(
        f'(?P<name>{CALLBACK_COMMAND_STATUS_UPDATE})'
    ),
    re.compile(
        r'^(?P<name>setinterval)[\s]+'
        r'(?P<action>adjust|set)[\s]+'
        r'(?P<interval>[1-7]?[0-9]{1,2})$'
    ),
    re.compile(
        r'^(?P<name>setmode)[\s]+'
        r'(?P<action>adjust|set)[\s]+'
        r'(?P<mode>auto|manual)$'
    ),
    re.compile(
        r'^(?P<name>setinitial)[\s]+'
        r'(?P<action>adjust|set)[\s]+'
        r'(?P<initial_sig>[0-3])$'
    ),
    re.compile(
        r'^(?P<name>settz)[\s]+'
        r'(?P<action>adjust|set)[\s]+'
        r'(?P<tz_offset>[+-]?(1[0-2]|\d))$'
    ),
)

MSG_SETTING_NUM_PREFIX = '🔢 **Изменение настройки**:\n\n'
MSG_SETTING_STR_PREFIX = '🔠 **Изменение настройки**:\n\n'

MSG_SETINTERVAL = (
    MSG_SETTING_NUM_PREFIX
    + '⚙️ Интревал между 🚬:  **{interval}**  мин\n\n⬇'
)

MSG_SETMODE = (
    MSG_SETTING_STR_PREFIX
    + '⚙️ Перезапуск таймера:  {mode}\n\n⬇'
)

MSG_SETINITIAL = (
    MSG_SETTING_NUM_PREFIX
    + '⚙️ Сигарет в начале: **{initial_sig}**\n\n⬇'
)

MSG_SETTZ = (
    MSG_SETTING_NUM_PREFIX
    + '⚙️ Часовой пояс: **UTC{tz_offset:+}**\n\n⬇'
)
