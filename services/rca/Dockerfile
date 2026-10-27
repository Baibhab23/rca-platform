FROM python:3.11-slim
WORKDIR /app
COPY services/rca/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared /app/shared
COPY services/rca /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
