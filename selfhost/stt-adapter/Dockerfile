FROM python:3.11-slim

WORKDIR /srv

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STT_MODELS_DIR=/models

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py protocol.py recognizer.py ./

RUN mkdir -p /models
EXPOSE 8092

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8092"]
