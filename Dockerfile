# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt \
 && pip install --no-cache-dir --prefix=/install gunicorn

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    WATCH_FILE=/data/watchlist.json \
    STATE_FILE=/data/state.json
RUN useradd -r -u 1000 -m -d /app app \
 && mkdir -p /data && chown app:app /data
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=app:app . .
USER app
VOLUME ["/data"]
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen(f'http://127.0.0.1:{__import__(\"os\").environ.get(\"PORT\",5000)}/').read()" || exit 1
CMD ["sh", "-c", "gunicorn -w 2 -b 0.0.0.0:${PORT} --access-logfile - app:app"]
