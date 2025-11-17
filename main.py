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
ROBOT_API = os.getenv("ROBOT_API")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

processador = ProcessaAudio()

async def enviar_comando_robo(acao: str, valor: int | None = None):
    if not ROBOT_API:
        return "Robô não configurado."
    try:
        payload = {"acao": acao}
        if valor is not None:
            payload["valor"] = valor
        r = requests.post(f"{ROBOT_API}/comando", json=payload, timeout=5)
        return r.json().get("resposta", "OK") if r.ok else "Erro no robô"
    except:
        return "Falha na comunicação com o robô"

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        m4a_data = await websocket.receive_bytes()
        reconhecedor = processador.criar_reconhecedor()
        texto = processador.transcrever(reconhecedor, m4a_data).strip()
        if not texto:
            await websocket.send_text("Não entendi o áudio.")
            return

        texto_lower = texto.lower()
        resposta = "Desculpe, não entendi."

        if any(chave in texto_lower for chave in ["lyria", "líria", "liria"]):

            if any(frase in texto_lower for frase in ["para frente", "pra frente", "anda pra frente", "vai pra frente", "de um passo", "dê um passo", "1 passo", "um passo", "ande 10", "10 centímetros", "10 cm"]):
                await enviar_comando_robo("frente", 10)
                resposta = "Andando 10 cm para frente."

            elif "ande bastante" in texto_lower or "vai bastante" in texto_lower:
                await enviar_comando_robo("frente", 30)
                resposta = "Andando 30 cm para frente."

            elif any(frase in texto_lower for frase in ["para trás", "pra trás", "anda pra trás", "recua", "recue"]):
                await enviar_comando_robo("tras", 15)
                resposta = "Andando para trás."

            elif any(frase in texto_lower for frase in ["esquerda", "à esquerda", "vire esquerda", "vira esquerda"]):
                await enviar_comando_robo("esquerda", 90)
                resposta = "Virando à esquerda."

            elif any(frase in texto_lower for frase in ["direita", "à direita", "vire direita", "vira direita"]):
                await enviar_comando_robo("direita", 90)
                resposta = "Virando à direita."

            elif any(frase in texto_lower for frase in ["parar", "pare", "stop", "freia", "freie"]):
                await enviar_comando_robo("parar")
                resposta = "Parando."

            if resposta != "Desculpe, não entendi.":
                await websocket.send_text(resposta)
                return

        if API_BACK:
            try:
                r = requests.post(
                    f"{API_BACK}/Lyria/conversar",
                    json={"pergunta": texto, "persona": "professor"},
                    timeout=15
                )
                resposta = r.json().get("resposta", resposta) if r.ok else "Estou com problema agora."
            except:
                resposta = "Não consegui responder agora."

        await websocket.send_text(resposta)

    except Exception as e:
        logger.error(f"Erro: {e}", exc_info=True)
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()