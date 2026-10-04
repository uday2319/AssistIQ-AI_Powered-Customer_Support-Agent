FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir \
    torch==2.14.0 \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir \
    --default-timeout=300 \
    -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["sh","-c","uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]