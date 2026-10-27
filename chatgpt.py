import os
import re
import random
import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import requests

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
CHATGPT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-6-luna")
CHATGPT_MAX_ATTEMPTS = 3
CHATGPT_REQUEST_TIMEOUT = (2, 5)
CHATGPT_API_URL = "https://api.openai.com/v1/chat/completions"
CHATGPT_API_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {OPENAI_API_KEY}",
}
# we remove this shit
CHATGPT_REMOVE_PATTERNS = [
    r'извините\S*\s*',
    r'как (ai|ии)\S+\s*',
    r'как искусствен\S* интеллект\S*',
    r'как виртуальный ассистент\S*',
    r'не имею (чувств и )?личных предпочтений\S*',
]
# if we see this shit, we try again
CHATGPT_FILTER_PATTERNS = [
    r'\b(Evan|Эван)\b',
    r'\b(pact|пакт)\b',
    r'летний парен[её]к',
    r'не могу',
    r'\b(вы|вам|ваш)\b',
    r'искусствен\S+ интеллект',
    r'не имею (личных )?предпочтений',
    r'не имею (особого )?мнения',
    r'не обладаю (свободной )?волей',
    r'не имею личности',
    r'не обладаю чувствами',
    r'не могу выразить (личное )?отношение',
    r'ai-ассистент',
    r'персонаж',
    r'экспертиз',
]


def retry_delay(response, attempt):
    """Honor server backoff only when it fits this synchronous webhook."""
    delay = min(2 ** attempt + random.uniform(0, 0.25), 2)
    retry_after = response.headers.get('Retry-After') if response is not None else None
    if retry_after:
        try:
            server_delay = float(retry_after)
        except ValueError:
            try:
                server_delay = (parsedate_to_datetime(retry_after) -
                                datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                server_delay = 0
        delay = max(delay, server_delay)
    return delay if delay <= 2 else None


def call_chatgpt(user, prompt, history=None, max_tokens=1000, stop=None, temperature=1.0,
                 on_success=None):
    messages = [{"role": "system", "content": """Ты - Evan (Эван), персонаж из из вселенной Pact или как будто ты 12-летний паренек.
Отвечай как можно короче, желательно одним предложением. Обращайся к собеседнику на ты"""}]
    messages.extend(history or [])
    user_message = {"role": "user", "content": prompt}
    if user['username']:
        user_message['name'] = user['username']
    messages.append(user_message)

    data = {
        "model": CHATGPT_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if CHATGPT_MODEL == 'gpt-6-luna' or CHATGPT_MODEL.startswith('gpt-6-luna-'):
        data['reasoning_effort'] = 'none'
        data['max_completion_tokens'] = max_tokens
    else:
        data['max_tokens'] = max_tokens
    if stop is not None:
        data['stop'] = stop
    message = None
    for attempt in range(CHATGPT_MAX_ATTEMPTS):
        response = None
        try:
            response = requests.post(
                CHATGPT_API_URL, headers=CHATGPT_API_HEADERS, json=data,
                timeout=CHATGPT_REQUEST_TIMEOUT)
        except (requests.Timeout, requests.ConnectionError) as exc:
            logger.warning('OpenAI transport error: %s', type(exc).__name__)
        else:
            if response.status_code == 200 and on_success is not None:
                on_success()
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            if response.status_code != 200:
                error = payload.get('error') or {} if isinstance(payload, dict) else {}
                if not isinstance(error, dict):
                    error = {}
                code = error.get('code')
                error_type = error.get('type')
                logger.warning('OpenAI HTTP %s, model=%s, code=%s, type=%s',
                               response.status_code, CHATGPT_MODEL, code, error_type)
                if (response.status_code not in (408, 429, 500, 502, 503, 504) or
                        code in ('insufficient_quota', 'billing_hard_limit_reached') or
                        error_type == 'insufficient_quota'):
                    return None
            else:
                try:
                    content = payload['choices'][0]['message']['content']
                    if not isinstance(content, str) or not content.strip():
                        return None
                except (KeyError, IndexError, TypeError):
                    logger.warning('OpenAI returned no text choice')
                    return None
                message = content.strip('.').strip('"').strip()
                for pattern in CHATGPT_REMOVE_PATTERNS:
                    message = re.sub(pattern, "", message, flags=re.IGNORECASE)
                if not any(re.search(pattern, message, re.IGNORECASE)
                           for pattern in CHATGPT_FILTER_PATTERNS):
                    return message
                logger.info('Retrying filtered OpenAI response')

        if attempt + 1 < CHATGPT_MAX_ATTEMPTS:
            delay = retry_delay(response, attempt)
            if delay is None:
                return None
            time.sleep(delay)

    return message.strip('.').strip('"').strip() if message else None
