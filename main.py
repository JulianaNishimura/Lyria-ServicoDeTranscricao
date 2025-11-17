import os
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

# Verificar se arquivos existem no startup
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
        # Detectar e converter automaticamente WAV ou WebM
        logger.info("Converting audio format...")
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        audio = audio.set_frame_rate(16000).set_channels(1)
        
        # Salvar em arquivo temporário
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)
        wav_data = wav_io.read()
        
        logger.info(f"Converted audio size: {len(wav_data)} bytes")
        
        # Verificar se o binário existe
        if not Path(WHISPER_CPP).exists():
            logger.error(f"Whisper binary not found at {WHISPER_CPP}")
            return ""
        
        if not Path(MODEL_PATH).exists():
            logger.error(f"Model not found at {MODEL_PATH}")
            return ""

        # Executar whisper.cpp - REMOVIDO stderr para esconder warnings
        logger.info("Running whisper.cpp...")
        result = subprocess.run(
            [WHISPER_CPP, "-m", MODEL_PATH, "-f", "/dev/stdin", 
             "--language", "pt", "--threads", "4", "--no-timestamps"],
            input=wav_data,
            capture_output=True,
            timeout=15,
            stderr=subprocess.DEVNULL  # IGNORA os warnings do stderr
        )

        if result.returncode != 0:
            logger.error(f"Whisper process failed with code {result.returncode}")
            return ""

        texto = result.stdout.decode("utf-8", errors="ignore")
        logger.info(f"Raw whisper output: {texto[:300]}")
        
        # Processar saída - FILTRAR a linha de warning
        linhas = []
        for l in texto.split("\n"):
            l_strip = l.strip()
            # Ignorar linhas vazias, timestamps e WARNINGS
            if (l_strip and 
                not l_strip.startswith("[") and 
                "warning:" not in l_strip.lower() and
                "deprecated" not in l_strip.lower() and
                "whisper_main" not in l_strip.lower() and
                "github.com" not in l_strip.lower()):
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

        # Comandos de robô com wake word "lyria"
        if any(x in texto for x in ["lyria", "líria", "liria"]):
            logger.info(f"Wake word detected in: {texto}")
            
            if any(x in texto for x in ["frente", "pra frente", "passo"]):
                if "30" in texto or "bastante" in texto or "trinta" in texto:
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

            # Se comando foi reconhecido, enviar resposta e retornar
            if resposta != "Desculpe, não entendi.":
                logger.info(f"Enviando resposta: {resposta}")
                audio_response = texto_para_audio(resposta)
                if audio_response and websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_bytes(audio_response)
                    logger.info("Áudio de resposta enviado")
                return

        # Fallback para API de conversação
        if API_BACK:
            try:
                logger.info(f"Enviando para API_BACK: {texto}")
                r = requests.post(
                    f"{API_BACK}/Lyria/conversar", 
                    json={"pergunta": texto, "persona": "professor"}, 
                    timeout=15
                )
                if r.ok:
                    resposta = r.json().get("resposta", resposta)
                    logger.info(f"Resposta da API: {resposta}")
                else:
                    logger.error(f"API_BACK returned {r.status_code}")
            except Exception as e:
                logger.error(f"Erro ao chamar API_BACK: {e}")

        audio_response = texto_para_audio(resposta)
        if audio_response and websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_bytes(audio_response)
            logger.info("Áudio de resposta enviado")

    except Exception as e:
        logger.error(f"Erro no WebSocket: {e}", exc_info=True)
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
            logger.info("WebSocket closed")