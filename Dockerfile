FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git build-essential cmake ffmpeg wget libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/ggerganov/whisper.cpp.git /app/whisper.cpp && \
    cd /app/whisper.cpp && \
    WHISPER_NO_AVX=1 make -j$(nproc) main

RUN ln -s /app/whisper.cpp/main /usr/local/bin/whisper-cli && \
    chmod +x /app/whisper.cpp/main

RUN wget -q -O /app/ggml-tiny.bin \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV WHISPER_CLI=/usr/local/bin/whisper-cli
ENV MODEL_PATH=/app/ggml-tiny.bin
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]
