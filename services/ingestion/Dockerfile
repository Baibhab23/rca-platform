FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y librdkafka-dev gcc && rm -rf /var/lib/apt/lists/*
COPY services/ingestion/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared /app/shared
COPY services/ingestion /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
