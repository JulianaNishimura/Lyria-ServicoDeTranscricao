import os
import logging
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState  # ⬅️ IMPORTANTE
from processa_audio import ProcessaAudio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BACK = os.getenv("API_do_BACK")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

processador = ProcessaAudio()

@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    reconhecedor = processador.criar_reconhecedor()

    try:
        while True:
            webm_chunk = await websocket.receive_bytes()
            texto = processador.transcrever(reconhecedor, webm_chunk)

            if not texto:
                continue

            logger.info(f"Transcrição: '{texto}'")

            resposta = "Desculpe, não entendi."
            if API_BACK:
                try:
                    import requests
                    r = requests.post(
                        f"{API_BACK}/Lyria/conversar",
                        json={"pergunta": texto, "persona": "social"},
                        timeout=10
                    )
                    if r.ok:
                        resposta = r.json().get("resposta", resposta)
                except Exception as e:
                    logger.error(f"Erro na IA: {e}")

            audio_bytes = processador.texto_para_audio(resposta)
            await websocket.send_bytes(audio_bytes)

    except Exception as e:
        logger.error(f"Erro no WebSocket: {e}")
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()