# Sgt_Smoker

Бот для бросания курить - контролирует предварительно заданное время между сигаретами и выдает разрешение на перекур :) 

В момент написания данного документа бот живет по адресу https://t.me/Sgt_Smoker_bot

### Usage

Общение с ботом осуществляется с помощью кнопки меню внизу экрана. 

После запуска бота (`/start`) пользователь может установить настройки:
- интервал в минутах между сигаретами (`/setinterval 60`)
- начальное кол-во доступных сигарет после запуска таймера (`/setinitial 1`)
- часовой пояс (`/settz 3` UTC+3)

После запуска таймера (`/run`), для получения разрешения используется команда `/smoke` - далее просто выполняйте инструкции бота.

Текущий статус (кол-во доступных сигарет, время до следующей) доступны по команде `/status`

Пред сном остановите бота командой `/stop` - ему тоже нужно отдыхать :)

### Stack

- Python 3.11
- python-telegram-bot 20.6

### Dev-deployment

Клонируйте репозиторий
```
git clone https://github.com/AV31459/Sgt_Smoker.git
```
Создайте и установите виртуальное окружение
```
cd Sgt_Smoker
python3 -m venv env
source env/bin/activate
```
Установите зависимости
```
pip install -r requirements.txt
```
*Переименуйте и отредактируйте файл с токеном бота и telegram_id его администратора*
```
mv .env.examle .env
vi .env (или любым другим текстовым редактором по вкусу)
```
Локальный запуск бота
```
python3 smoker_bot.py
```

### Author

AV31459 - [AV31459](https://github.com/AV31459)  