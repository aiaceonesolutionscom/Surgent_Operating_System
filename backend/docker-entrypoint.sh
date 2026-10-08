#!/bin/sh
# Container entrypoint.
#
#   RUN_MIGRATIONS=true  -> `alembic upgrade head` before the server starts.
#                           Safe with ONE instance. With several replicas run
#                           migrations as a separate release step instead, so
#                           two instances never migrate at once.
#
# Exactly one uvicorn worker, on purpose: the WhatsApp / follow-up / nurture
# pollers live inside the app process, and a second worker or replica would
# process every message twice.
set -e

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "Running database migrations..."
    alembic upgrade head
fi

# --proxy-headers: behind the platform's load balancer request.client.host is
# the proxy; trust X-Forwarded-For so rate-limit keys and audit IPs are real.
exec uvicorn src.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips="*"
