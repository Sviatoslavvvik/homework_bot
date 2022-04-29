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
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
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


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logging.INFO(f'Удачная отправка сообщения "{message}"')
    bot.send_message(TELEGRAM_CHAT_ID, message)
    if Exception:
        logging.ERROR('сбой при отправке сообщения')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if homework_statuses.status_code != HTTPStatus.OK:
        logging.ERROR('сбой при доступе к эндпойнту')
        raise NotCorrectResponse("Код ответа не 200")
    return homework_statuses.json()


def check_response(response):
    """Проверят ответ на корректность."""
    if type(response) != dict:
        logging.ERROR('Ответ имеет тип не словарь')
        raise TypeError('Ответ не в виде словаря')
    if HOMEWORK_KEY not in response.keys():
        logging.ERROR('Отсутствует ожидаемый ключ')
        raise NotCorrectResponse('Ответ не содержит ключа homeworks')
    if type(response.get(HOMEWORK_KEY)) != list:
        logging.ERROR('Поле имеет тип не list')
        raise NotCorrectResponse('Домашки приходят не в виде списка')
    return response.get(HOMEWORK_KEY)


def parse_status(homework):
    """Получает статус работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES.keys():
        raise KeyError('Статус работы не существует')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID


def main():
    """Основная логика работы бота."""
    previous_error = None
    if not check_tokens():
        logging.CRITICAL(
            'отсутствие обязательных переменных окружения'
            ' во время запуска бота'
        )
        raise EnvVariableAbsent('Переменная окружения недоступна')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks != []:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(bot, message)
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
            logging.DEBUG("Отсутствие в ответе нового статуса")

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if error is KeyError:
                logging.ERROR(
                    'недокументированный статус домашней работы,'
                    ' обнаруженный в ответе'
                )
            if previous_error != error:
                send_message(bot, message)
                previous_error = error
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
