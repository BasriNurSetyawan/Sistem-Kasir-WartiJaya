FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py ./config.py
COPY app/ ./app/

ENV PORT=7860
EXPOSE 7860

CMD ["python", "-m", "app.run"]
