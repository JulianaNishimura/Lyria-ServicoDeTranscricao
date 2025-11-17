import os
import tempfile
import io
import logging
import requests
import subprocess
from pathlib import Path
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
from pydub import AudioSegment
from gtts import gTTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BACK = os.getenv("API_do_BACK")
ROBOT_API = os.getenv("ROBOT_API")

WHISPER_CLI = os.getenv("WHISPER_CLI", "/app/whisper.cpp/build/bin/whisper-cli")
MODEL_PATH   = os.getenv("MODEL_PATH", "/app/ggml-tiny.bin")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup_event():
    logger.info(f"whisper-cli exists: {Path(WHISPER_CLI).exists()}")
    logger.info(f"Model exists: {Path(MODEL_PATH).exists()}")

def transcrever_whisper(audio_bytes: bytes) -> str:
    if len(audio_bytes) < 1500:
        return ""  # áudio muito curto

    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            audio.export(tmp_path, format="wav")

        result = subprocess.run(
            [
                WHISPER_CLI,
                "-m", MODEL_PATH,
                "-f", tmp_path,
                "-l", "pt",
                "--no-timestamps",
                "--print-color", "false",
                "--output-file", "-",  # printa no stdout
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # mais rápido
            timeout=15
        )

        os.remove(tmp_path)

        if result.returncode != 0:
            return ""

        texto = result.stdout.decode("utf-8", errors="ignore").strip().lower()

        # limpeza simples e RÁPIDA
        texto = texto.replace("\n", " ").strip()

        return texto

    except subprocess.TimeoutExpired:
        logger.error("Whisper timeout")
        return ""
    except Exception as e:
        logger.error(f"Erro Whisper: {e}")
        return ""

def texto_para_audio(texto: str) -> bytes:
    try:
        tts = gTTS(text=texto or "Desculpe, não entendi.", lang="pt")
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.error(f"TTS erro: {e}")
        return b""

async def enviar_comando_robo(acao: str, valor=None):
    if not ROBOT_API:
        return
    try:
        payload = {"acao": acao}
        if valor is not None:
            payload["valor"] = valor
        requests.post(f"{ROBOT_API}/comando", json=payload, timeout=3)
    except:
        pass

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        data = await websocket.receive_bytes()

        texto = transcrever_whisper(data)
        if not texto:
            resposta = "não entendi"
        else:
            resposta = "Desculpe, não entendi."

        # wake word
        if any(x in texto for x in ["lyria", "liria", "líria"]):

            if "frente" in texto:
                await enviar_comando_robo("frente", 10)
                resposta = "Andando para frente."

            elif "trás" in texto or "tras" in texto or "recuar" in texto:
                await enviar_comando_robo("tras", 10)
                resposta = "Andando para trás."

            elif "esquerda" in texto:
                await enviar_comando_robo("esquerda")
                resposta = "Virando à esquerda."

            elif "direita" in texto:
                await enviar_comando_robo("direita")
                resposta = "Virando à direita."

            elif "parar" in texto:
                await enviar_comando_robo("parar")
                resposta = "Parando."

        # enviar áudio final
        audio_resp = texto_para_audio(resposta)
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_bytes(audio_resp)

    except Exception as e:
        logger.error(f"WS erro: {e}")

    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
