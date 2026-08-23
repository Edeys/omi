FROM python:3.11-slim

WORKDIR /srv

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=8)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
