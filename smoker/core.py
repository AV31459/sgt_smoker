import time
import datetime as dt

from telegram.ext import ContextTypes, JobQueue
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from . import const


def is_int(value: str) -> bool:
    """Check if string value can be converted to int type."""
    try:
        int(value)
        return True
    except ValueError:
        return False


def get_start_message(update: Update) -> str:
    """Formats start message based on given update."""
    return const.START_MSG.format(
        update.effective_user.first_name
    )


def get_settings_message(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Formats settings message based on given context."""
    return const.SETTINGS_MSG.format(
        context.user_data['interval'],
        context.user_data['initial_sig'],
        context.user_data['tz_offset'],
    )


def get_setting_success_msg(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Formats successful setting change message based on given context."""
    return const.SETTING_SUCCESS_PREFIX + get_settings_message(context)


def check_user_data(user_data: dict) -> bool:
    """Cheks if all requred keys present in user_data."""
    return (user_data and all(x in user_data for x in const.INITIAL_USER_DATA))


def check_or_reset_user_data(user_data: dict) -> None:
    """Cheks if all requred keys present in user_data, resets it overwise."""
    if not check_user_data(user_data):
        user_data.clear()
        user_data.update(const.INITIAL_USER_DATA)


def get_time_string(posix_time: int, tz_offset: int) -> str:
    """Create time string given POSIX time and time zone offset."""
    return (
        dt.datetime.fromtimestamp(
            posix_time,
            dt.timezone(dt.timedelta(hours=tz_offset))
        ).strftime('%H:%M')
    )


def get_timedelta_string(seconds: int) -> str:
    """Create hh:mm(.ss) string from timedelta in seconds."""
    hh_mm = (
        f'{seconds // const.SECONDS_IN_HOUR:02d}:'
        f'{(seconds % const.SECONDS_IN_HOUR) // const.SECONDS_IN_MINUTE:02d}'
    )
    if seconds > const.SECONDS_IN_MINUTE - 1:
        return hh_mm
    else:
        return f'00:00\\.{seconds:02d}'


def get_status_message(user_data: dict) -> str:
    """Formats status message based on given context."""
    current_time = int(time.time())
    if user_data['is_running']:
        return const.STATUS_RUNNING_MSG.format(
            user_data['sig_available'],
            get_time_string(user_data['interval_end'], user_data['tz_offset']),
            get_timedelta_string(
                max(0, user_data['interval_end'] - current_time)
            ),
            get_time_string(current_time, user_data['tz_offset'])
        )
    return const.STATUS_STOPPED_MSG


def get_wakeup_error_meaasge(context: ContextTypes.DEFAULT_TYPE):
    """Formats job wakeup error message."""
    return (const.ERROR_CHECK_SETTINGS_MSG
            + get_settings_message(context)
            + get_status_message(context.user_data))


def get_new_cig_avalable_message(context: ContextTypes.DEFAULT_TYPE):
    """Formats new cigarette available message."""
    return const.NEW_CIG_AVALABLE_MSG.format(
        context.user_data['sig_available']
    )


def get_smoked_cigs_message(context: ContextTypes.DEFAULT_TYPE):
    """Formats smoked cigarettes message."""
    return const.STOP_SMOKED_CIGS_MSG.format(
        context.user_data['sig_smoked']
    )


def remove_user_jobs(user_id: int, job_queue: JobQueue):
    """Clean user wakeup jobs by user_id."""
    for job in job_queue.get_jobs_by_name(str(user_id) + '_wakeup'):
        job.schedule_removal()


def drop_user_data_and_jobs(user_id: int,
                            context: ContextTypes.DEFAULT_TYPE):
    """Delete all user data and jobs."""
    remove_user_jobs(user_id, context.application.job_queue)
    context.application.drop_user_data(user_id)


def get_inline_keyboard_update() -> InlineKeyboardMarkup:
    """Create InlineKeyboardMarkup with one 'status_update' button."""
    return InlineKeyboardMarkup(
        ((InlineKeyboardButton('Обновить', callback_data='status_update'),),)
    )


def get_default_reply_message(update: Update):
    return const.DEFAULT_REPLY_MSG.format(update.message.text_markdown_v2)


def get_bot_started_message(context: ContextTypes.DEFAULT_TYPE):
    return const.BOT_STARTED_MSG.format(len(context.application.user_data))
