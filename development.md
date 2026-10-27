# Local development

The supported local runtime is Python 3.11 in Docker. The bot receives Telegram
messages through long polling and stores reply-chain history in SQLite.
Use a separate development bot token: starting the polling runner removes the
webhook for that token while preserving pending updates.

## Configuration

Create `.env` from `.env.example` and `config.py` from `config.dist.py` if they do
not already exist. Use development credentials in both files. Neither file is
tracked by Git or included in the image. The container reads `config.py` through
a read-only mount; it must be readable by container UID 10001.

`.env` contains the Telegram token, OpenAI key, and runtime settings.
`config.py` contains bot names, administrators, chapter mappings, and the existing
Smartcat/S3 integration settings. Chatting uses Telegram and OpenAI; translation
and export commands additionally need their integration credentials.

Set `ALLOWED_GROUP_IDS` to the Telegram group and supergroup IDs that may use
the bot, and `ALLOWED_USER_IDS` to user IDs that may contact it privately.
`ADMIN_USER_IDS` grants both private access and permission to use `/assign`,
`/revoke`, and `/clear_executives`. Existing username-based administrators in
`ADMIN_USERS` retain those same permissions and private access; prefer user IDs
for new administrators. All lists in the template are empty, so access is denied
until configured. Group access depends on the group ID, even for administrators.
The allowlists are checked before any handler, including commands and greetings.
Actual IDs belong in the ignored `config.py`; restart the service after changes.

| Variable | Default | Meaning |
| --- | --- | --- |
| `TELEGRAM_TOKEN` | Required | Development bot token |
| `OPENAI_API_KEY` | Required | OpenAI API key |
| `OPENAI_MODEL` | `gpt-6-luna` | Chat Completions model |
| `LOG_LEVEL` | `INFO` | Application logging level |
| `HISTORY_MAX_MESSAGES` | `20` | Maximum previous messages in a reply chain |
| `HISTORY_MAX_CHARS` | `16000` | Maximum combined characters in previous messages |
| `HISTORY_RETENTION_DAYS` | `7` | Age after which stored messages expire |
| `DAILY_USER_MESSAGE_LIMIT` | `30` | Paid messages per user across all chats per UTC day |
| `DAILY_GROUP_MESSAGE_LIMIT` | `100` | Paid messages per group per UTC day |

Compose sets `HISTORY_DB_PATH=/data/history.sqlite3` and
`HEARTBEAT_PATH=/data/heartbeat`. Adjust these paths when running the Python
entry point outside Docker.

## Run locally

With development credentials configured:

```bash
docker compose -p evan-bot-dev up --build -d
docker compose -p evan-bot-dev logs -f bot
docker compose -p evan-bot-dev ps
```

The service exposes no ports, runs as a non-root user with a read-only root
filesystem, and has CPU, memory, process, and log-size limits. `/tmp` is temporary;
`/data` is a named volume. The health check expects a recent successful polling
heartbeat. `restart: unless-stopped` restarts an exited process; a failed health
check alone does not restart it.

After changing code, repeat `up --build -d`. To stop the local service:

```bash
docker compose -p evan-bot-dev down
```

Ordinary container replacement and `down` preserve history. Removing the named
volume removes the database and the saved Telegram update offset.

## Reply-chain history and cleanup

`history.py` stores each message with its chat ID, topic ID, Telegram message ID,
parent message ID, role, content, and optional username. `bot.py` follows only the
ancestors of the message being replied to. A new message without a reply has no
previous context, even in a private chat. Replying to an older message creates a
branch without including later sibling replies.

Only exchanges handled by the bot's ordinary text handler are recorded. Telegram
does not provide an arbitrary historical transcript: an unknown quoted bot
message can seed a chain, but older ancestors cannot be reconstructed. Existing
command handlers and member greetings are not automatically added to history.

Reads exclude expired records immediately. Cleanup deletes expired records on
startup, hourly during polling, and when new exchanges are saved. SQLite reuses
freed database pages; deleting records does not necessarily shrink the file.
Cleanup applies to this local history, not to messages in Telegram. Message text
is not logged by the ordinary chat handler.

## Daily usage limits

The bot reserves a user slot and, in groups, a group slot before calling OpenAI.
Each Telegram message is counted once after the first HTTP 200 response, including
when subsequent retries are needed to filter a response. API errors without a
successful response release the reservation. Commands, canned responses, rejected
updates and quota-exceeded replies do not consume slots. Both limits apply to
admins as well. Counts reset at midnight UTC and survive container restarts.
The database discards usage records older than seven days during cleanup.

Each reservation is atomic. Unfinished reservations are removed at startup, so
only one polling instance may use the database. An API request that times out
after reaching OpenAI can have an unknown billing outcome; the bot cannot count
that as a confirmed successful response. These message limits are not a monetary
spending cap, and filtered retries can incur multiple API calls per message.

`run.py` saves the next Telegram update ID after processing each update. History
and offsets survive process restarts. A crash after sending a reply but before
saving the offset can still cause a duplicate reply; delivery is not exactly-once.
Run only one polling instance for a bot token.

## Tests

The test image uses placeholder configuration and mocked Telegram/OpenAI calls:

```bash
docker build --target test -t evan-bot-tests .
docker run --rm --network none evan-bot-tests
```

Tests cover branch isolation, chat/topic boundaries, persistence across reopened
database connections, retention and cleanup, context limits, polling offsets,
reply handling, and API error/retry behavior. The test target is separate from
the default production image and contains no real credentials.

The repository contains old platform-specific `lxml` binaries and a legacy
virtual environment may target an unavailable Python version. The Docker build
installs compatible dependencies and excludes those local artifacts.

## Legacy code

`handlers/webhook.py` and `serverless.yml` remain for compatibility with the old
Lambda webhook. The polling service starts at `run.py`; persistent conversation
history requires its SQLite store. No cloud database is used for history.
