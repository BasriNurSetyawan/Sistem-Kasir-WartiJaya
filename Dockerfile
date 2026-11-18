FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/toko_warti_jaya.db

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py ./config.py
COPY app/ ./app/
COPY algorithm/ ./algorithm/
COPY migrations/ ./migrations/

RUN useradd -m -u 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data
USER appuser

ENV PORT=7860
EXPOSE 7860
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT', '7860') + '/healthz', timeout=3)" || exit 1

CMD ["sh", "-c", "flask --app app.run db upgrade && flask --app app.run bootstrap-admin && waitress-serve --host=0.0.0.0 --port=${PORT:-7860} app.run:app"]
