from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse
from processa_audio import ProcessaAudio 
import io
import os
import requests

API_BACK = os.environ.get("API_do_BACK")

app = FastAPI()
processador_audio = ProcessaAudio()

origins = [
    "http://localhost:8080",
    "api do mobile",
    "api do front para garantir",
    "api do back"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True,
    allow_methods=["GET","POST"],  
    allow_headers=["ver os headers depois"],  
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Conexão WebSocket aceita.")
    reconhecedor_voz = processador_audio.create_recognizer()
    try:
        while True:
            audio_data = await websocket.receive_bytes()
            transcricao = processador_audio.transcribe_audio(reconhecedor_voz, audio_data)
            
            if transcricao:
                try:
                    response_ai = requests.post(API_BACK + "/Lyria/conversar", json={"pergunta": transcricao})
                    response_ai.raise_for_status()

                    resposta_texto = response_ai.json().get("resposta", "Desculpe, não consegui entender.")
                except requests.exceptions.RequestException:
                    resposta_texto = "Desculpe, não consegui me conectar com a IA."
                
                audio_bytes = processador_audio.synthesize_text_to_speech(resposta_texto)
                if audio_bytes:
                    await websocket.send_bytes(audio_bytes)
    except WebSocketDisconnect:
        print("Cliente desconectado.")
    except Exception as e:
        print(f"Erro na conexão WebSocket: {e}")
