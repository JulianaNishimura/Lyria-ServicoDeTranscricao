import os
import logging
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
from processa_audio import ProcessaAudio
import requests

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

        logger.info(f"🗣️ Texto reconhecido: '{texto}'")

        t = texto.lower()

        comando = False

        if "frente" in t or "lyria ande para a frente" in t:
            logger.info("✅ COMANDO DETECTADO: FRENTE")
            comando = True

        if "trás" in t or "tras" in t:
            logger.info("✅ COMANDO DETECTADO: TRÁS")
            comando = True

        if "esquerda" in t:
            logger.info("✅ COMANDO DETECTADO: ESQUERDA")
            comando = True

        if "direita" in t:
            logger.info("✅ COMANDO DETECTADO: DIREITA")
            comando = True

        if comando:
            await websocket.send_text("")
            return

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
                logger.error(f"Erro na IA: {e}")

        await websocket.send_text(resposta)
        logger.info(f"📤 Texto enviado ao cliente: {resposta}")

    except Exception as e:
        logger.error(f"Erro no WebSocket: {e}", exc_info=True)
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
