import os
import io
import json
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def transcrever_whisper(m4a_bytes: bytes) -> str:
    try:
        audio = AudioSegment.from_file(io.BytesIO(m4a_bytes), format="m4a")
        audio = audio.set_frame_rate(16000).set_channels(1)
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)

        result = subprocess.run([
            WHISPER_CPP,
            "-m", MODEL_PATH,
            "-f", "/dev/stdin",
            "--language", "pt",
            "--max-len", "1",
            "--no-timestamps",
            "--threads", "4"
        ], input=wav_io.read(), capture_output=True, timeout=12)

        texto = result.stdout.decode("utf-8", errors="ignore")
        linhas = [l.strip() for l in texto.split("\n") if l.strip() and not l.startswith("[")]
        return " ".join(linhas).strip().lower()

    except subprocess.TimeoutExpired:
        logger.warning("Whisper demorou demais")
        return ""
    except Exception as e:
        logger.error(f"Erro no Whisper: {e}")
        return ""

def texto_para_audio(texto: str) -> bytes:
    tts = gTTS(text=texto or "Desculpe, não entendi.", lang="pt", slow=False)
    buffer = io.BytesIO()
    tts.write_to_fp(buffer)
    buffer.seek(0)
    return buffer.read()

async def enviar_comando_robo(acao: str, valor: int | None = None):
    if not ROBOT_API:
        return
    try:
        payload = {"acao": acao}
        if valor is not None:
            payload["valor"] = valor
        requests.post(f"{ROBOT_API}/comando", json=payload, timeout=5)
    except:
        pass

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        m4a_data = await websocket.receive_bytes()
        logger.info(f"Recebido áudio: {len(m4a_data)} bytes")

        texto = transcrever_whisper(m4a_data)
        if not texto:
            texto = "não entendi o áudio"

        logger.info(f"Transcrito: '{texto}'")
        resposta = "Desculpe, não entendi."

        if any(nome in texto for nome in ["lyria", "líria", "liria"]):
            if any(cmd in texto for cmd in ["frente", "um passo", "10 cm", "10 centímetros", "pra frente"]):
                await enviar_comando_robo("frente", 10)
                resposta = "Andando 10 centímetros para frente."

            elif any(cmd in texto for cmd in ["bastante", "30 cm"]):
                await enviar_comando_robo("frente", 30)
                resposta = "Andando 30 centímetros para frente."

            elif any(cmd in texto for cmd in ["trás", "recua", "recue"]):
                await enviar_comando_robo("tras", 15)
                resposta = "Andando para trás."

            elif "esquerda" in texto:
                await enviar_comando_robo("esquerda", 90)
                resposta = "Virando à esquerda."

            elif "direita" in texto:
                await enviar_comando_robo("direita", 90)
                resposta = "Virando à direita."

            elif any(cmd in texto for cmd in ["parar", "pare", "stop", "freia"]):
                await enviar_comando_robo("parar")
                resposta = "Parando."

            if resposta != "Desculpe, não entendi.":
                audio = texto_para_audio(resposta)
                await websocket.send_bytes(audio)
                return

        if API_BACK:
            try:
                r = requests.post(
                    f"{API_BACK}/Lyria/conversar",
                    json={"pergunta": texto, "persona": "professor"},
                    timeout=15
                )
                if r.ok:
                    resposta = r.json().get("resposta", resposta)
            except:
                resposta = "Tô com um probleminha agora, tenta de novo."

        audio_resposta = texto_para_audio(resposta)
        await websocket.send_bytes(audio_resposta)

    except Exception as e:
        logger.error(f"Erro no WebSocket: {e}", exc_info=True)
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()