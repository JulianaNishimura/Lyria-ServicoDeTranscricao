import os
import io
import logging
import requests
import subprocess
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
from pydub import AudioSegment
from gtts import gTTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BACK = os.getenv("API_do_BACK")
ROBOT_API = os.getenv("ROBOT_API")
WHISPER_CPP = "/app/whisper.cpp/main"
MODEL_PATH = "/app/whisper.cpp/models/ggml-tiny.bin"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def transcrever_whisper(audio_bytes: bytes) -> str:
    if len(audio_bytes) < 2000:
        return ""
    try:
        # Aceita WAV ou WebM automaticamente
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        audio = audio.set_frame_rate(16000).set_channels(1)
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)

        result = subprocess.run(
            [WHISPER_CPP, "-m", MODEL_PATH, "-f", "/dev/stdin", "--language", "pt", "--threads", "4"],
            input=wav_io.read(), capture_output=True, timeout=10
        )

        texto = result.stdout.decode("utf-8", errors="ignore")
        linhas = [l.strip() for l in texto.split("\n") if l.strip() and not l.startswith("[")]
        final = " ".join(linhas).strip().lower()
        logger.info(f"Transcrito: '{final}'")
        return final
    except Exception as e:
        logger.error(f"Erro Whisper: {e}")
        return ""

def texto_para_audio(texto: str) -> bytes:
    tts = gTTS(text=texto or "Desculpe, não entendi.", lang="pt", slow=False)
    buffer = io.BytesIO()
    tts.write_to_fp(buffer)
    buffer.seek(0)
    return buffer.read()

async def enviar_comando_robo(acao: str, valor: int | None = None):
    if ROBOT_API:
        try:
            requests.post(f"{ROBOT_API}/comando", json={"acao": acao, "valor": valor} if valor else {"acao": acao}, timeout=5)
        except:
            pass

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_bytes()
        logger.info(f"Áudio recebido: {len(data)} bytes")

        texto = transcrever_whisper(data)
        if not texto:
            texto = "não entendi"

        resposta = "Desculpe, não entendi."

        if any(x in texto for x in ["lyria", "líria", "liria"]):
            if any(x in texto for x in ["frente", "pra frente", "passo", "10 cm"]):
                await enviar_comando_robo("frente", 10)
                resposta = "Andando 10 centímetros para frente."
            elif "30" in texto or "bastante" in texto:
                await enviar_comando_robo("frente", 30)
                resposta = "Andando 30 centímetros para frente."
            elif any(x in texto for x in ["trás", "recua"]):
                await enviar_comando_robo("tras", 15)
                resposta = "Andando para trás."
            elif "esquerda" in texto:
                await enviar_comando_robo("esquerda")
                resposta = "Virando à esquerda."
            elif "direita" in texto:
                await enviar_comando_robo("direita")
                resposta = "Virando à direita."
            elif any(x in texto for x in ["parar", "pare", "stop"]):
                await enviar_comando_robo("parar")
                resposta = "Parando."

            if resposta != "Desculpe, não entendi.":
                await websocket.send_bytes(texto_para_audio(resposta))
                return

        if API_BACK:
            try:
                r = requests.post(f"{API_BACK}/Lyria/conversar", json={"pergunta": texto, "persona": "professor"}, timeout=15)
                resposta = r.json().get("resposta", resposta) if r.ok else resposta
            except:
                pass

        await websocket.send_bytes(texto_para_audio(resposta))

    except Exception as e:
        logger.error(f"Erro: {e}", exc_info=True)
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()