FROM python:3.11-slim
WORKDIR /app
COPY services/governance/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared /app/shared
COPY services/governance /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]
