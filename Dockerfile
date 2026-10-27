FROM python:3.11-slim-bookworm AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-docker.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements-docker.txt

FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --gid 10001 evan && useradd --uid 10001 --gid evan --no-create-home evan \
    && mkdir /app /data && chown evan:evan /data
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
WORKDIR /app
COPY bot.py chatgpt.py constants.py helpers.py history.py links.py run.py strings.py ./
COPY commands/ ./commands/
COPY smartcat/ ./smartcat/
USER 10001:10001
CMD ["python", "run.py"]

FROM runtime AS test
USER root
RUN pip install --no-cache-dir pytest==9.1.1
COPY config.dist.py pytest.ini ./
COPY tests/ ./tests/
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/unit"]

FROM runtime AS production
