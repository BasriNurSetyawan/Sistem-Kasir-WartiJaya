FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py ./config.py
COPY app/ ./app/
COPY migrations/ ./migrations/

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

ENV PORT=5000
EXPOSE 5000

CMD ["sh", "-c", "flask --app app.run db upgrade && flask --app app.run bootstrap-admin && waitress-serve --host=0.0.0.0 --port=${PORT:-5000} app.run:app"]
