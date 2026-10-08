FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 app
COPY --chown=app:app . .
RUN chmod +x docker-entrypoint.sh
USER app

# The platform injects PORT (InsForge compute passes --port as the container
# port); 8000 is the fallback for plain `docker run`.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=4)"

ENTRYPOINT ["./docker-entrypoint.sh"]
