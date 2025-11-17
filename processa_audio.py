import os
import json
import logging
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
from vosk import Model, KaldiRecognizer
import requests
import wave
import io

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

model = Model("model-pt")


def transcrever_audio(audio_bytes):
    audio_stream = io.BytesIO(audio_bytes)
    try:
        with wave.open(audio_stream, "rb") as wav:
            rec = KaldiRecognizer(model, wav.getframerate())
            rec.AcceptWaveform(wav.readframes(wav.getnframes()))
            result = json.loads(rec.Result())
            return result.get("text", "")
    except:
        return ""


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        m4a_data = await websocket.receive_bytes()
        texto = transcrever_audio(m4a_data)
        if not texto:
            texto = "Não entendi o áudio."

        texto_normalizado = texto.lower().strip()
        resposta = "Desculpe, não entendi."
        comando_enviado = False
        distancia = 10
        endpoint_robo = None

        def extrair_direcao(t):
            direcoes = {
                "frente": "move_forward",
                "para frente": "move_forward",
                "pra frente": "move_forward",
                "trás": "move_backward",
                "para trás": "move_backward",
                "pra trás": "move_backward",
                "esquerda": "turn_left",
                "direita": "turn_right",
            }
            for k, v in direcoes.items():
                if k in t:
                    return v
            return None

        if texto_normalizado.startswith("lyria"):
            comando = texto_normalizado[6:].strip()
            endpoint_robo = extrair_direcao(comando)
            if endpoint_robo:
                comando_enviado = True

            if comando == "de 1 passo":
                endpoint_robo = "move_forward"
                distancia = 10
                comando_enviado = True

            if comando == "ande 10 centimetros":
                endpoint_robo = "move_forward"
                distancia = 10
                comando_enviado = True

            if comando == "ande bastante":
                endpoint_robo = "move_forward"
                distancia = 30
                comando_enviado = True

        else:
            endpoint_robo = extrair_direcao(texto_normalizado)
            if endpoint_robo:
                comando_enviado = True

        if comando_enviado:
            if ROBOT_API and endpoint_robo:
                try:
                    r = requests.post(
                        f"{ROBOT_API}/{endpoint_robo}",
                        json={"distance_cm": distancia},
                        timeout=5
                    )
                    if r.ok:
                        resposta = f"Executando comando: {texto_normalizado}"
                    else:
                        resposta = "Erro ao enviar comando para o robô."
                except:
                    resposta = "Erro ao conectar com o robô."
            else:
                resposta = "ROBOT_API não configurado."

        if not comando_enviado:
            if API_BACK:
                try:
                    r = requests.post(
                        f"{API_BACK}/Lyria/conversar",
                        json={"pergunta": texto, "persona": "professor"},
                        timeout=10
                    )
                    if r.ok:
                        resposta = r.json().get("resposta", resposta)
                except:
                    pass

        await websocket.send_text(resposta)

    except:
        pass
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
