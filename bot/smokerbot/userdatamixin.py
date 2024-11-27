from dataclasses import asdict, dataclass

import yaml

from . import const, context
from .basehandler import BaseHandler
from .exceptions import ContextValuetError


@dataclass
class UserData:
    # User status
    is_active_user: bool        # False if blocked by user, True otherwise

    # Service status
    is_running: bool
    is_timer: bool

    # Settings
    mode: str                   # {'auto', 'manual'} - timer restart mode
    interval: int               # timer interval lenght, minutes
    initial_sig: int            # sig available after service start
    tz_offset: int              # timezone offset vs UTC

    # Current run data
    ran_at: float | None        # service run at, POSIX
    sig_available: int          # Current sig available
    sig_smoked: int             # sigs smoked so far
    timer_start: float | None   # timer started at, POSIX
    timer_end: float | None     # timer end time, POSIX


class UserdataMixin:
    """Методы работы с пользовательскими данными."""

    manage_context = BaseHandler.manage_context

    @manage_context
    def _get_default_userdata(self) -> UserData:
        """Создать объект пользовательских данных по умолчанию."""

        return UserData(**const.USER_DATA_DEFAULT)

    @manage_context
    def _load_userdata(self):
        """Загрузка пользовательских данных."""

        if (filename := (self.data_path / 'userdata.yaml')).is_file():
            with filename.open('r') as f:
                self._users = {
                    k: UserData(**v) for k, v in yaml.safe_load(f).items()
                }

            self.logger.info(f'{context.get_task_prefix()} User data loaded')

    @manage_context
    def _save_userdata(self):
        """Сохранение пользовательских данных."""

        with open(self.data_path / 'userdata.yaml', 'w') as file:
            yaml.safe_dump(
                {k: asdict(v) for k, v in self._users.items()},
                file,
                indent=4
            )

        self.logger.info(f'{context.get_task_prefix()} User data persisted')

    @manage_context
    def _get_or_create_userdata(self, user_id: int | None = None) -> UserData:
        """Получить или создать дефолтный объект данных пользователя.

        Если аргумент `user_id` не был передан, используется `sender_id` из
        текущего контекста.
        """

        if not (user_id or (user_id := context.sender_id.get())):
            raise ContextValuetError('no \'sender_id\' set in context')

        if not (userdata := self._users.get(user_id)):
            self._users[user_id] = (userdata := self._get_default_userdata())

        return userdata

    @manage_context
    def _get_settings_string(self) -> str:
        """Сформировать строку сообщения с настройками пользователя."""

        userdata = self._get_or_create_userdata()

        return const.MSG_SETTINGS.format(
            interval=userdata.interval,
            mode=(
                const.STR_MODE_AUTO if userdata.mode == 'auto'
                else const.STR_MODE_MANUAL
            ),
            initial_sig=userdata.initial_sig,
            tz_offset=userdata.tz_offset
        )
