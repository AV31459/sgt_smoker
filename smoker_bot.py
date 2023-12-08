import logging
import os
import time
from logging.config import dictConfig

from dotenv import load_dotenv
from telegram import MenuButtonCommands, Update, error
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CallbackContext,
                          CallbackQueryHandler, CommandHandler, ContextTypes,
                          MessageHandler, PersistenceInput, PicklePersistence,
                          filters)

from smoker import const, core
from smoker import settings as _settings

dictConfig(_settings.LOG_CONFIG)
logger = logging.getLogger(__name__)
logger.setLevel(_settings.BOT_LOG_LEVEL)

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')


async def bot_init(context: ContextTypes.DEFAULT_TYPE):
    """Initialize bot after (re)start."""
    logger.debug('bot_init() called')
    await context.bot.set_my_commands(const.BOT_COMMANDS)
    await context.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    logger.info('Bot is being started, registered users count: '
                f'{len(context.application.user_data)}')

    for user_id in context.application.user_data:
        logger.debug(f'bot_init(): found data for user_id={user_id}, '
                     f'data={context.application.user_data[user_id]} '
                     'scheduling wake up job')
        context.job_queue.run_once(
            callback=user_wakeup,
            when=1,
            user_id=user_id,
            name=str(user_id) + '_wakeup'
        )
    await context.application.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=core.get_bot_started_message(context),
        parse_mode=ParseMode.MARKDOWN_V2
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f'start() handler called, '
                 f'user_id={update.effective_user.id}, '
                 f'user_data={context.user_data}')
    core.check_or_reset_user_data(context.user_data)
    await update.effective_message.reply_markdown_v2(
        core.get_start_message(update)
    )


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f'help() handler called, user_id={update.effective_user.id}')
    await update.effective_message.reply_markdown_v2(const.HELP_MSG)


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug('settings() handler called, '
                 f'user_id={update.effective_user.id}, '
                 f'args={context.args}')
    core.check_or_reset_user_data(context.user_data)
    await update.effective_message.reply_markdown_v2(
        core.get_settings_message(context)
    )


async def setinterval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f'setinterval() handler called, args={context.args}, '
                 f'user_id={update.effective_user.id}')
    if not (len(context.args) == 1 and core.is_int(context.args[0])
            and int(context.args[0]) > 0):
        await update.effective_message.reply_markdown_v2(
            const.SETINTERVAL_ERROR_MSG)
        return
    context.user_data['interval'] = int(context.args[0])
    await update.effective_message.reply_markdown_v2(
        core.get_setting_success_msg(context)
    )


async def setinitial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f'setinitial() handler called, args={context.args}, '
                 f'user_id={update.effective_user.id}')
    if not (len(context.args) == 1 and core.is_int(context.args[0])
            and int(context.args[0]) >= 0):
        await update.effective_message.reply_markdown_v2(
            const.SETINITIAL_ERROR_MSG
        )
        return
    context.user_data['initial_sig'] = int(context.args[0])
    await update.effective_message.reply_markdown_v2(
        core.get_setting_success_msg(context)
    )


async def settz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f'settz() handler called, args={context.args}, '
                 f'user_id={update.effective_user.id}')
    if not (len(context.args) == 1 and core.is_int(context.args[0])
            and int(context.args[0]) in range(-12, 13)):
        await update.effective_message.reply_markdown_v2(
            const.SETTZ_ERROR_MSG
        )
        return
    context.user_data['tz_offset'] = int(context.args[0])
    await update.effective_message.reply_markdown_v2(
        core.get_setting_success_msg(context)
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f'handler called for user_id={update.effective_user.id}')
    await update.effective_message.reply_markdown_v2(
        core.get_status_message(context.user_data),
        reply_markup=(
            core.get_inline_keyboard_update()
            if context.user_data['is_running']
            else None
        )
    )


async def status_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f'handler called for user_id={update.effective_user.id}')
    await update.callback_query.answer()
    updated_message = core.get_status_message(context.user_data)
    if (updated_message.strip()
            == update.callback_query.message.text_markdown_v2):
        return
    await update.callback_query.edit_message_text(
        text=updated_message,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=core.get_inline_keyboard_update()
    )


async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data['is_running']:
        logger.debug(f'user_id={update.effective_user.id}: '
                     'timer is already running, sending info message only')
        await update.effective_message.reply_markdown_v2(
            const.RUN_ALREADY_RUNNING_MSG
        )
        return

    logger.debug(f'user_id={update.effective_user.id}: setting timer as '
                 'running, setting up wakeup job and sending user status msg')
    current_time = int(time.time())
    wakeup_seconds = context.user_data['interval'] * const.SECONDS_IN_MINUTE
    context.user_data['is_running'] = True
    context.user_data['sig_available'] = context.user_data['initial_sig']
    context.user_data['sig_smoked'] = 0
    context.user_data['ran_at'] = current_time
    context.user_data['interval_start'] = current_time
    context.user_data['interval_end'] = current_time + wakeup_seconds
    context.job_queue.run_once(
        callback=user_wakeup,
        when=wakeup_seconds,
        user_id=update.effective_user.id,
        name=str(update.effective_user.id) + '_wakeup'
    )
    await status(update, context)


async def user_wakeup(context: CallbackContext):
    user_id = context.job.user_id
    user_data = context.user_data

    logger.debug(f'user_wakeup() called, iser_id= {user_id}, '
                 f'user_data={user_data}')

    if not (core.check_user_data(user_data) and user_data['is_running']):
        logger.debug(f'user_wakeup() with iser_id={user_id}: exiting with no '
                     'action (no user_data or is_running=False)')
        return

    current_time = int(time.time())
    wakeup_seconds = user_data['interval'] * const.SECONDS_IN_MINUTE

    if (current_time < user_data['interval_start']
            or current_time > user_data['interval_end'] + wakeup_seconds):
        logger.debug(f'user_wakeup() with iser_id={user_id}: wakeup with '
                     'error - sending error message, current_time='
                     f'{current_time} is out of reasoanble bounds')
        user_data['is_running'] = False
        await context.bot.send_message(
            chat_id=user_id,
            text=core.get_wakeup_error_meaasge(context),
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    elif current_time < user_data['interval_end']:
        logger.debug(f'user_wakeup() with iser_id={user_id}: early wakeup - '
                     'current interval is not yet over, recheduling')
        context.job_queue.run_once(
            callback=user_wakeup,
            when=(user_data['interval_end'] - current_time),
            user_id=user_id,
            name=str(user_id) + '_wakeup'
        )
        return

    logger.debug(f'user_wakeup() with iser_id={user_id} - normal wakeup: '
                 'increasing available cigarette counter, moving '
                 'interval, scheduling next wake up and informing user')
    user_data['sig_available'] += 1
    user_data['interval_start'] = user_data['interval_end']
    user_data['interval_end'] += wakeup_seconds
    context.job_queue.run_once(
        callback=user_wakeup,
        when=wakeup_seconds,
        user_id=user_id,
        name=str(user_id) + '_wakeup'
    )
    await context.bot.send_message(
        chat_id=user_id,
        text=core.get_new_cig_avalable_message(context),
        parse_mode=ParseMode.MARKDOWN_V2
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data['is_running']:
        logger.debug(f'stop() handler, user_id={update.effective_user.id}: '
                     'stoppping timer, removing jobs, sending the number of '
                     'smoked cigs and status msg')
        context.user_data['is_running'] = False
        core.remove_user_jobs(update.effective_user.id, context.job_queue)
        await update.effective_message.reply_markdown_v2(
            core.get_smoked_cigs_message(context)
        )
    else:
        logger.debug(f'stop() handler, user_id={update.effective_user.id}: '
                     'timer is already stopped, sending status only')
    await status(update, context)


async def smoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data['is_running']:
        logger.debug(f'user_id={update.effective_user.id}, timer is stopped, '
                     'sending negative and status msg')
        reply = const.SMOKE_NEGATIVE_STOPPED_TIMER
    elif context.user_data['sig_available'] > 0:
        logger.debug(f'user_id={update.effective_user.id}, '
                     f'sig_available={context.user_data["sig_available"]}:'
                     'de(in)crementing sig_available(sig_smoked) counters, '
                     'sending user confirmationg and status msg')
        context.user_data['sig_available'] -= 1
        context.user_data['sig_smoked'] += 1
        reply = const.SMOKE_AFFIRMATIVE_MSG
    else:
        logger.debug(f'user_id={update.effective_user.id}, '
                     f'sig_available={context.user_data["sig_available"]}:'
                     'no sigarettes available, send negative and status msg')
        reply = const.SMOKE_NEGATIVE_NO_SIG_AVAILABLE
    await update.effective_message.reply_markdown_v2(reply)
    await status(update, context)


async def default_handler(update: Update,
                          context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug(f'called, user_id={update.effective_user.id}, '
                 f'message={update.message.text}')
    await update.effective_message.reply_markdown_v2(
        core.get_default_reply_message(update)
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, error.NetworkError):
        logger.error(f'Network error {context.error} of type '
                     f'{type(context.error)}), suppressing exc_info')
    elif isinstance(context.error, error.Forbidden):
        user_id = update.effective_user.id if update else context.job.user_id
        logger.info(
            f'{context.error} for user_id={user_id}, '
            f'deleting all user data and jobs.'
        )
        core.drop_user_data_and_jobs(user_id, context)
        if not context.user_data.get(user_id):
            logger.info(f'user_id={user_id} data deleted successfully')
    else:
        logger.error(
           f'Unhandled error : {context.error}', exc_info=context.error
        )


if __name__ == '__main__':
    """Main bot runner."""
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .persistence(
            PicklePersistence(
                filepath=_settings.USERDATA_FILEPATH,
                store_data=PersistenceInput(
                    bot_data=False, chat_data=False,
                    user_data=True, callback_data=False
                ),
            )
        )
        .build()
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help))
    application.add_handler(CommandHandler('settings', settings))
    application.add_handler(CommandHandler('setinterval', setinterval))
    application.add_handler(CommandHandler('setinitial', setinitial))
    application.add_handler(CommandHandler('settz', settz))
    application.add_handler(CommandHandler('status', status))
    application.add_handler(CommandHandler('run', run))
    application.add_handler(CommandHandler('stop', stop))
    application.add_handler(CommandHandler('smoke', smoke))
    application.add_handler(
        CallbackQueryHandler(status_update, pattern='status_update')
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, default_handler)
    )
    application.add_error_handler(error_handler)

    application.job_queue.run_once(bot_init, .1,
                                   job_kwargs={'misfire_grace_time': None})

    application.run_polling()
