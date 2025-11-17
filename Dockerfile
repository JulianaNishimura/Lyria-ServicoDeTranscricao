FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git build-essential cmake libopenblas-dev ffmpeg wget \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN git clone https://github.com/ggerganov/whisper.cpp.git && \
    cd whisper.cpp && \
    cmake -B build && \
    cmake --build build --config Release && \
    ./models/download-ggml-model.sh tiny

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]