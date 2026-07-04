import os
from dotenv import load_dotenv
import requests
import logging
import sys
import time
import vk_api

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)
load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
VK_TOKEN = os.getenv("VK_TOKEN")
VK_USER_ID = os.getenv("VK_USER_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


def check_tokens():
    """Функция для проверки наличия необходимых данных"""
    return all([PRACTICUM_TOKEN, VK_TOKEN, VK_USER_ID])


def send_message(vk, message):
    """Отправляет сообщение в VK-чат."""
    try:
        vk.messages.send(user_id=VK_USER_ID, message=message, random_id=0)
        logging.debug(f'Сообщение отправлено: "{message}"')
    except Exception as error:
        logging.error(f"Сбой при отправке : {error}")
        raise error


def get_api_answer(timestamp):
    """Функция для получения ответа от сервера и обработка ошибок"""
    params = {"from_date": timestamp}
    try:
        print(f"DEBUG ОТПРАВКИ: URL={ENDPOINT}, HEADERS={HEADERS}, PARAMS={params}")
        response = requests.get(ENDPOINT, params=params, headers=HEADERS)
    except requests.RequestException as error:
        raise ConnectionError(f"ошибка при отправке запроса к API")

    if response.status_code != 200:
        raise ValueError(f"Эндпоинт недоступен. Код ошибки {response.status_code}")

    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError("Ответ API должен быть словарем")
    if "homeworks" not in response:
        raise KeyError('В ответе API отсутствует ключ "homeworks"')
    if not isinstance(response["homeworks"], list):
        raise TypeError('Значение по ключу "homeworks" должно быть списком')
    return True


def parse_status(homework):
    """Извлекает из информации о домашней работе её статус."""

    if "homework_name" not in homework:
        raise ValueError('В ответе API отсутствует ключ "homework_name"')

    if "status" not in homework:
        raise ValueError('В ответе API отсутствует ключ "status"')

    homework_name = homework["homework_name"]
    status = homework["status"]

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f"Неожиданный статус домашней работы: {status}")

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical(
            "Отсутствует обязательная переменная окружения! "
            "Программа принудительно остановлена."
        )
        sys.exit("Критическая ошибка: проверьте переменные окружения.")

    try:
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
    except Exception as error:
        logging.critical(f"Ошибка инициализации VK API: {error}")
        sys.exit(f"Не удалось запустить VK сессию: {error}")

    timestamp = int(time.time())

    last_error = ""

    while True:
        try:
            response = get_api_answer(timestamp)

            check_response(response)

            homeworks = response.get("homeworks")

            if homeworks:
                message = parse_status(homeworks[0])
                send_message(vk, message)
            else:
                logging.debug("Отсутствие в ответе новых статусов.")

            timestamp = response.get("current_date", timestamp)

            last_error = ""

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logging.error(message)

            if message != last_error:
                try:
                    send_message(vk, message)
                    last_error = message
                except Exception as vk_err:
                    logging.error(
                        f"Не удалось отправить отчет об ошибке в VK: {vk_err}"
                    )

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
