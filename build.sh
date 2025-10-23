echo "Instalando FFmpeg..."
apt-get update && apt-get install -y ffmpeg

echo "Instalando dependências Python..."
pip install -r requirements.txt