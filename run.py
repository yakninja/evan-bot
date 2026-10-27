"""Single-process Telegram long polling with durable offsets and reply history."""
import logging
import os
from pathlib import Path
import signal
import time
from threading import Event

from telegram.error import Conflict, NetworkError, RetryAfter

import bot as application
from history import HistoryStore

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO'),
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    store = HistoryStore(
        os.environ.get('HISTORY_DB_PATH', '/data/history.sqlite3'),
        max_messages=int(os.environ.get('HISTORY_MAX_MESSAGES', '20')),
        max_chars=int(os.environ.get('HISTORY_MAX_CHARS', '16000')),
        retention_days=int(os.environ.get('HISTORY_RETENTION_DAYS', '7')),
        daily_user_limit=int(os.environ.get('DAILY_USER_MESSAGE_LIMIT', '30')),
        daily_group_limit=int(os.environ.get('DAILY_GROUP_MESSAGE_LIMIT', '100')))
    application.history_store = store
    application.usage_store = store
    logger.info('Removed %s unfinished usage reservations', store.clear_pending_usage())
    logger.info('Removed %s expired history messages', store.prune())
    next_cleanup = time.monotonic() + 3600
    heartbeat = Path(os.environ.get('HEARTBEAT_PATH', '/data/heartbeat'))
    stopping = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopping.set())

    client = application.bot
    identity = client.get_me()
    offset = store.next_update_id(identity.id)
    # Switching to polling disables the previous webhook, preserving queued updates.
    client.delete_webhook(drop_pending_updates=False)
    logger.info('Polling as @%s; reply-chain history enabled', identity.username)
    while not stopping.is_set():
        try:
            if time.monotonic() >= next_cleanup:
                logger.info('Removed %s expired history messages', store.prune())
                next_cleanup = time.monotonic() + 3600
            updates = client.get_updates(offset=offset, timeout=20, read_latency=5,
                                         allowed_updates=['message'])
            heartbeat.touch()
            for update in updates:
                if stopping.is_set():
                    break
                application.dispatcher.process_update(update)
                offset = update.update_id + 1
                store.acknowledge(identity.id, offset)
                heartbeat.touch()
        except Conflict:
            logger.exception('Another poller or webhook is active; stopping')
            raise
        except RetryAfter as exc:
            logger.warning('Telegram rate limit; waiting %s seconds', exc.retry_after)
            stopping.wait(exc.retry_after)
        except NetworkError:
            logger.warning('Telegram network error; retrying in 5 seconds')
            stopping.wait(5)
    logger.info('Polling stopped cleanly')


if __name__ == '__main__':
    main()
