FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN useradd --create-home rx && mkdir -p /data && chown -R rx /data /app
USER rx

EXPOSE 8000
CMD ["sh", "./entrypoint.sh"]
