import datetime as dt
import math

from telethon import types
from telethon.tl.custom.message import Message

from . import const


def get_command_from_string(string: str) -> dict:
    """If string matches some *command* regex returns `re.Match.groupdict()`.

    Note: Returned dict keys correspond to regex group names as defined in
    original regex expressions.
    For groups with certian names, defined in const.BOT_COMMAND_INT_RE_GROUPS,
    string values are converted to python `int` for convenience.
    """

    for canonical_name, pattern in const.BOT_COMMAND_NAME_RE_DICT.items():
        if (
            (match := pattern.match(string))
            and (command := match.groupdict())
        ):
            command['name'] = canonical_name

            for group_name in const.BOT_COMMAND_INT_RE_GROUPS:
                if command.get(group_name):
                    command[group_name] = int(command[group_name])

            return command


def get_callback_command_from_string(string: str) -> dict:
    """If str matches  *callback command* regex returns `re.Match.groupdict()`.

    Note: Returned dict keys correspond to regex group names as defined in
    original regex expressions.
    For groups with certian names, defined in const.BOT_COMMAND_INT_RE_GROUPS,
    string values are converted to python `int` for convenience.
    """

    for pattern in const.BOT_CALLBACK_COMMANDS_RE:
        if (
            (match := pattern.match(string))
            and (command := match.groupdict())
        ):
            for group_name in const.BOT_COMMAND_INT_RE_GROUPS:
                if command.get(group_name):
                    command[group_name] = int(command[group_name])

            return command


def get_emoji_reaction_from_msg(msg: Message, user_id: int) -> str | None:
    """Get `ReactionEmoji.emoticon` string set by given `user_id` if any."""

    if not (msg.reactions and msg.reactions.recent_reactions):
        return

    for peer_reaction in msg.reactions.recent_reactions:
        if not (
            isinstance(peer_reaction.peer_id, types.PeerUser)
            and peer_reaction.peer_id.user_id == user_id
        ):
            continue

        if isinstance(peer_reaction.reaction, types.ReactionEmoji):
            return peer_reaction.reaction.emoticon

        return 'not_an_instance_of_ReactionEmoji'


def trunc(message: str | None, n: int = 40):
    """Truncates long string to *n* symbols adding trailng [...] if needed."""

    if isinstance(message, str):
        return message[:n] + ('[...]' if len(message) > n else '')

    return message


def get_chat_at_id_string(msg: Message) -> str:
    """Get *'[ chat_id @ id ]:'* string for `telethone.Message`."""

    return f'[ {msg.chat_id} @ {msg.id} ]:'


def get_message_info_string(msg: Message) -> str:
    """Get brief attributes string for `telethone.Message`."""

    return (
        f'chat_id={msg.chat_id}, msg.id={msg.id}, '
        f'sender_id={msg.sender_id}, peer_id={msg.peer_id}, '
        f'from_id={msg.from_id}, '
        f'fwd_from.from_id={msg.fwd_from.from_id if msg.fwd_from else None}, '
        f'action={msg.action}, message="{trunc(msg.message)}"'
    )


def get_time_string(posix_time: float, tz_offset: int) -> str:
    """Get time string given POSIX time and time zone offset."""

    return (
        dt.datetime.fromtimestamp(
            posix_time,
            dt.timezone(dt.timedelta(hours=tz_offset))
        ).strftime('%H:%M')
    )


def get_timedelta_string(seconds: float) -> str:
    """Get hh:mm{.ss} string from timedelta in seconds."""

    seconds = math.ceil(seconds)

    return (
        (f'{seconds // const.SECONDS_IN_HOUR:02d}: '
         f'{(seconds % const.SECONDS_IN_HOUR) // const.SECONDS_IN_MINUTE:02d}')
        if (seconds > const.SECONDS_IN_MINUTE - 1)
        else f'00:00.{seconds:02d}'
    )


def get_wakeup_task_name(user_id: int) -> str:
    """Получить имя задачи wakeup для пользователя c данным user_id.

    Строковое имя: `wakeup @ <user_id>`
    """

    return f'wakeup @ {user_id}'
