## Deploy

```bash
export AWS_PROFILE=...
export TELEGRAM_TOKEN="..."
export WEBHOOK_PATH="..."
export SLS_STAGE=prod|dev
serverless deploy
```

You will get the endpoint url here. Use some secret stuff for the webhook path, for example, telegram token
without the colon (not allowed in path)

## Webhook setup

```bash
curl --request POST \
--url https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook \
--header 'content-type: application/json' \
--data '{"url": "{ENDPOINT_URL}"}'
```

On success, you will get:

```bash
{"ok":true,"result":true,"description":"Webhook was set"}
```

To remove webhook:

```bash
curl --request POST \
--url https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook
```