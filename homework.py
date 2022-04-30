import os
import sys
import time
import requests
from http import HTTPStatus
import logging

import telegram

from dotenv import load_dotenv

from exceptions import EnvVariableAbsent, NotCorrectResponse

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[logging.FileHandler(
        filename="main.log",
        encoding='utf-8',
        mode='a'),
        logging.StreamHandler(sys.stdout)],
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_KEY = 'homeworks'
HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

SOME_DELAY = 10


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(f'Удачная отправка сообщения "{message}"')
    except Exception:
        logging.exception('сбой при отправке сообщения')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except ConnectionError:
        logging.error('сбой при доступе к эндпойнту')
    if homework_statuses.status_code != HTTPStatus.OK:
        logging.error('сбой при доступе к эндпойнту')
        raise NotCorrectResponse("Код ответа не 200")
    try:
        full_response = homework_statuses.json()
    except Exception:
        logging.error('response не преобразуется в json')
    return full_response


def check_response(response):
    """Проверят ответ на корректность."""
    if not isinstance(response, dict):
        logging.error('Ответ имеет тип не словарь')
        raise TypeError('Ответ не в виде словаря')
    if HOMEWORK_KEY not in response.keys():
        logging.error('Отсутствует ожидаемый ключ')
        raise NotCorrectResponse('Ответ не содержит ключа homeworks')
    homeworks = response.get(HOMEWORK_KEY)
    if not isinstance(homeworks, list):
        logging.error('Поле имеет тип не list')
        raise NotCorrectResponse('Домашки приходят не в виде списка')
    return homeworks


def parse_status(homework):
    """Получает статус работы."""
    try:
        homework_name = homework.get('homework_name')
    except Exception:
        logging.error('Невозможно прочитать словарь')
    if homework_name is None:
        logging.error('Имя работы не найдено')
        raise KeyError('Имени работы не существует')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES.keys():
        logging.error('Статус работы не существует')
        raise KeyError('Статус работы не существует')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    some_dict = {
        'Токен практикума': PRACTICUM_TOKEN,
        'Токен бота': TELEGRAM_TOKEN,
        'Токен чата': TELEGRAM_CHAT_ID,
    }

    for key, value in some_dict.items():
        if not value:
            logging.critical(f'{key} отсутствует')
            return False
        else:
            return True


def main():
    """Основная логика работы бота."""
    previous_error = None
    if not check_tokens():
        raise EnvVariableAbsent('Переменная окружения недоступна')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - SOME_DELAY

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks != []:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(bot, message)
            else:
                logging.debug("Отсутствие в ответе нового статуса")
            try:
                current_timestamp = int(
                    response.get('current_date')
                )
            except Exception:
                logging.error('Поле current_date отсутствует')
                current_timestamp = int(time.time())

            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if previous_error != error:
                send_message(bot, message)
                previous_error = error


if __name__ == '__main__':
    main()
