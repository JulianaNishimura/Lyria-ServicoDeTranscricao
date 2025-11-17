FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y git build-essential wget && \
    git clone https://github.com/ggerganov/whisper.cpp.git && \
    cd whisper.cpp && make && \
    ./models/download-ggml-model.sh tiny

COPY . .

ENV PORT=8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]