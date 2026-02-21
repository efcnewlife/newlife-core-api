FROM python:3.13-alpine
# .build-deps build-base libffi-dev git rust cargo openssl-dev
RUN apk add --update --no-cache --virtual .build-deps build-base libffi-dev

ENV \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  POETRY_VERSION=2.1.4 \
  POETRY_HOME="/opt/poetry" \
  POETRY_NO_INTERACTION=1 \
  POETRY_VIRTUALENVS_CREATE=false \
  POETRY_CACHE_DIR="/opt/poetry_cache"

ENV PATH="$POETRY_HOME/bin:$PATH"

RUN pip install --upgrade pip \
  && pip install --no-cache-dir "poetry==$POETRY_VERSION"

WORKDIR /app

COPY . /app/

RUN poetry config virtualenvs.create false \
  && poetry install --without dev --no-ansi --no-root

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

EXPOSE 8000

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
