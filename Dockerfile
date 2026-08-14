FROM python:3.14-alpine

COPY --from=ghcr.io/astral-sh/uv:0.12.4 /uv /uvx /bin/

# .build-deps build-base libffi-dev git rust cargo openssl-dev
RUN apk add --update --no-cache --virtual .build-deps build-base libffi-dev

ENV \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy \
  UV_PYTHON_DOWNLOADS=never \
  PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY . /app/

RUN uv sync --frozen --no-dev --no-install-project

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

EXPOSE 8000

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
