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
WHISPER_CPP = os.getenv("WHISPER_BIN", "/app/whisper.cpp/build/bin/main")
MODEL_PATH = os.getenv("MODEL_PATH", "/app/ggml-tiny.bin")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup_event():
    whisper_exists = Path(WHISPER_CPP).exists()
    model_exists = Path(MODEL_PATH).exists()

    logger.info(f"Whisper binary exists: {whisper_exists} at {WHISPER_CPP}")
    logger.info(f"Model exists: {model_exists} at {MODEL_PATH}")

    if not whisper_exists:
        logger.error("WHISPER BINARY NOT FOUND!")

    if not model_exists:
        logger.error("MODEL FILE NOT FOUND!")

def transcrever_whisper(audio_bytes: bytes) -> str:
    if len(audio_bytes) < 2000:
        logger.warning("Audio too short, skipping transcription")
        return ""

    try:
        logger.info("Converting audio format...")
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            audio.export(tmp_path, format="wav")

        logger.info(f"Converted audio size (file): {os.path.getsize(tmp_path)} bytes at {tmp_path}")

        if not Path(WHISPER_CPP).exists():
            logger.error(f"Whisper binary not found at {WHISPER_CPP}")
            os.remove(tmp_path)
            return ""

        if not Path(MODEL_PATH).exists():
            logger.error(f"Model not found at {MODEL_PATH}")
            os.remove(tmp_path)
            return ""

        logger.info("Running whisper.cpp...")
        result = subprocess.run(
            [
                WHISPER_CPP,
                "-m", MODEL_PATH,
                "-f", tmp_path,
                "--language", "pt",
                "--threads", "4",
                "--no-timestamps"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )

        os.remove(tmp_path)

        if result.returncode != 0:
            logger.error(f"Whisper process failed with code {result.returncode}")
            logger.error(f"Whisper stdout: {result.stdout.decode('utf-8', errors='ignore')[:800]}")
            logger.error(f"Whisper stderr: {result.stderr.decode('utf-8', errors='ignore')[:2000]}")
            return ""

        texto_raw = result.stdout.decode("utf-8", errors="ignore")
        logger.info(f"Raw whisper output: {texto_raw[:300]}")

        linhas = []
        for l in texto_raw.split("\n"):
            l_strip = l.strip()
            if (
                l_strip and
                not l_strip.startswith("[") and
                "warning:" not in l_strip.lower() and
                "deprecated" not in l_strip.lower() and
                "github.com" not in l_strip.lower()
            ):
                linhas.append(l_strip)

        final = " ".join(linhas).strip().lower()
        logger.info(f"Transcrito LIMPO: '{final}'")

        return final

    except subprocess.TimeoutExpired:
        logger.error("Whisper process timeout")
        return ""

    except Exception as e:
        logger.error(f"Erro Whisper: {e}", exc_info=True)
        return ""

def texto_para_audio(texto: str) -> bytes:
    try:
        tts = gTTS(text=texto or "Desculpe, não entendi.", lang="pt", slow=False)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        audio_bytes = buffer.read()
        logger.info(f"TTS gerou {len(audio_bytes)} bytes")
        return audio_bytes
    except Exception as e:
        logger.error(f"Erro TTS: {e}")
        return b""

async def enviar_comando_robo(acao: str, valor: int | None = None):
    if ROBOT_API:
        try:
            payload = {"acao": acao}
            if valor is not None:
                payload["valor"] = valor

            response = requests.post(f"{ROBOT_API}/comando", json=payload, timeout=5)
            logger.info(f"Robot command sent: {acao} {valor}, status: {response.status_code}")
        except Exception as e:
            logger.error(f"Erro ao enviar comando ao robô: {e}")

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "whisper_exists": Path(WHISPER_CPP).exists(),
        "model_exists": Path(MODEL_PATH).exists()
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    try:
        data = await websocket.receive_bytes()
        logger.info(f"Áudio recebido: {len(data)} bytes")

        texto = transcrever_whisper(data)
        if not texto:
            texto = "não entendi"
            logger.warning("Transcrição vazia ou falhou")

        resposta = "Desculpe, não entendi."

        if any(x in texto for x in ["lyria", "líria", "liria"]):
            logger.info(f"Wake word detected in: {texto}")

            if any(x in texto for x in ["frente", "pra frente", "passo"]):
                if any(x in texto for x in ["30", "trinta", "bastante"]):
                    await enviar_comando_robo("frente", 30)
                    resposta = "Andando 30 centímetros para frente."
                else:
                    await enviar_comando_robo("frente", 10)
                    resposta = "Andando 10 centímetros para frente."

            elif any(x in texto for x in ["trás", "recua", "recuar", "voltar"]):
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
                audio_response = texto_para_audio(resposta)
                if audio_response and websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_bytes(audio_response)
                    logger.info("Áudio de resposta enviado")
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
            except Exception as e:
                logger.error(f"Erro ao chamar API_BACK: {e}")

        audio_response = texto_para_audio(resposta)
        if audio_response and websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_bytes(audio_response)

    except Exception as e:
        logger.error(f"Erro no WebSocket: {e}", exc_info=True)

    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
            logger.info("WebSocket closed")
