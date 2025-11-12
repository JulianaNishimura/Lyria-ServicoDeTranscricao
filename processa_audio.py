import os
import io
import json
import logging
import requests
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
from vosk import Model, KaldiRecognizer
from gtts import gTTS
from pydub import AudioSegment

# Configuração de log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações da API
API_BACK = os.getenv("API_do_BACK")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Classe de processamento de áudio
# -------------------------------
class ProcessaAudio:
    def __init__(self, model_path="./vosk-model-small-pt-0.3"):
        self.model = Model(model_path)
        self.sample_rate = 16000

    def criar_reconhecedor(self):
        rec = KaldiRecognizer(self.model, self.sample_rate)
        rec.SetWords(True)
        return rec

    def transcrever(self, reconhecedor, audio_data: bytes):
        if not audio_data or len(audio_data) < 500:
            logger.warning("⚠️ Áudio recebido é muito pequeno ou vazio.")
            return None

        try:
            # Deixa o FFmpeg detectar o formato automaticamente
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
            audio = audio.set_frame_rate(self.sample_rate).set_channels(1).set_sample_width(2)
            pcm_data = audio.raw_data

            if reconhecedor.AcceptWaveform(pcm_data):
                resultado = json.loads(reconhecedor.Result())
            else:
                resultado = json.loads(reconhecedor.FinalResult())

            texto = resultado.get("text", "").strip()
            logger.info(f"🗣️ Texto reconhecido: '{texto}'")
            return texto

        except Exception as e:
            logger.error(f"❌ Erro na transcrição: {e}", exc_info=True)
            return None

    def texto_para_audio(self, texto: str) -> bytes:
        tts = gTTS(text=texto or "Desculpe, não entendi.", lang="pt", slow=False)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        return buffer.getvalue()

# -------------------------------
# WebSocket
# -------------------------------
processador = ProcessaAudio()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        m4a_data = await websocket.receive_bytes()
        logger.info(f"📥 Recebido áudio com {len(m4a_data)} bytes")

        reconhecedor = processador.criar_reconhecedor()
        texto = processador.transcrever(reconhecedor, m4a_data)

        if not texto:
            texto = "Não entendi o áudio."

        resposta = "Desculpe, não entendi."
        if API_BACK:
            try:
                r = requests.post(
                    f"{API_BACK}/Lyria/conversar",
                    json={"pergunta": texto, "persona": "professor"},
                    timeout=10
                )
                if r.ok:
                    resposta = r.json().get("resposta", resposta)
            except Exception as e:
                logger.error(f"Erro ao consultar API_BACK: {e}")

        audio_bytes = processador.texto_para_audio(resposta)
        await websocket.send_bytes(audio_bytes)

    except Exception as e:
        logger.error(f"Erro no WebSocket: {e}", exc_info=True)

    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
