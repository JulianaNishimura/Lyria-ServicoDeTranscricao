FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    libsndfile1 \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN wget -q https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip -O model.zip \
    && unzip model.zip \
    && rm model.zip \
    && mv vosk-model-small-pt-0.3 model

COPY . .

ENV MODEL_PATH=/app/model
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]

