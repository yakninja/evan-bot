import os
import re
import random 
import logging
import time
import requests

logger = logging.getLogger(__name__)

CHATGPT_API_KEY = os.environ['CHATGPT_KEY']
CHATGPT_API_URL = "https://api.openai.com/v1/chat/completions"
CHATGPT_API_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {CHATGPT_API_KEY}",
}
# we remove this shit
CHATGPT_REMOVE_PATTERNS = [
    r'извините\S*\s*',
    r'как (ai|ии)\S+\s*',
    r'как искусствен\S* интеллект\S*',
    r'как виртуальный ассистент\S*',
    r'(я )?не имею (чувств и )?личных предпочтений\S*',
]
# if we see this shit, we try again
CHATGPT_FILTER_PATTERNS = [
    r'\b(Evan|Эван)\b',
    r'\b(pact|пакт)\b',
    r'летний паренек',
    r'не могу',
    r' (вы|вам|ваш) ',
    r'искусствен\S+ интеллект',
    r'не имею (личных )?предпочтений',
    r'не имею (особого )?мнения',
    r'не обладаю (свободной )?волей',
    r'не имею личности',
    r'не обладаю чувствами',
    r'не могу выразить (личное )?отношение',
    r'ai-ассистент',
]

def call_chatgpt(user, prompt, max_tokens=1000, stop=None, temperature=1.0):
    tries = 0
    message = None
    while tries < 10:
        tries += 1
        content = prompt
        content += "\nОтветь одним предложением в стиле персонажа Evan (Эван) из вселенной Pact"
        if not random.randint(0, 1):
            content += " или как будто ты 12-летний паренек"
        data = {
            "model": "gpt-4" if tries == 1 else "gpt-3.5-turbo",
            "messages": [{"role": "user", "name": user['username'], "content": content}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stop": stop,
        }
        response = requests.post(
            CHATGPT_API_URL, headers=CHATGPT_API_HEADERS, json=data)
        if response.status_code != 200:
            logger.info(f'HTTP code: {response.status_code}, trying again in {tries}')
            time.sleep(tries)
            continue
        response = response.json()
        if 'choices' not in response:
            return None
        message = response["choices"][0]["message"]["content"]\
            .strip('.').strip('"').strip()
        print(message)
        for pattern in CHATGPT_REMOVE_PATTERNS:
            message = re.sub(pattern, "", message, flags=re.IGNORECASE)
        if not any(re.search(pattern, message, re.IGNORECASE) for pattern in CHATGPT_FILTER_PATTERNS):
            break
        logger.info(f'Skipped: {message}')
        time.sleep(tries)
    return message.strip('.').strip('"').strip() if message else None