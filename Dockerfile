FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    cmake \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/ggerganov/whisper.cpp.git && \
    cd whisper.cpp && \
    cmake -B build -DWHISPER_CUBLAS=OFF && \
    cmake --build build --config Release -- -j$(nproc)

RUN ls -lh /app/whisper.cpp/build/bin/ && \
    chmod +x /app/whisper.cpp/build/bin/main

RUN cd whisper.cpp && bash ./models/download-ggml-model.sh tiny

RUN cp whisper.cpp/models/ggml-tiny.bin /app/ggml-tiny.bin

RUN ls -lh /app/whisper.cpp/build/bin/main && \
    ls -lh /app/ggml-tiny.bin

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV WHISPER_BIN=/app/whisper.cpp/build/bin/main
ENV MODEL_PATH=/app/ggml-tiny.bin
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]