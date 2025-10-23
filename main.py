from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from processa_audio import ProcessaAudio 
import os
import io
import requests
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

API_BACK = os.environ.get("API_do_BACK")
WEBSOCKET_URL = os.environ.get("WEBSOCKET_URL", "ws://localhost:10000/ws")

if not API_BACK:
    logger.warning("⚠️ API_do_BACK não configurada! Configure no Render.")

app = FastAPI(title="Lyria - Serviço de Transcrição de Voz")
processador_audio = ProcessaAudio()

origins = [
    "http://localhost:8080",
    "http://localhost:5173",
    "http://127.0.0.1:8080",
    "https://teste-trasncricao-voz.onrender.com",
    "https://lyriafront.onrender.com",
    "https://lyria-back.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE", "PUT"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "User-Agent",
        "DNT",
        "Cache-Control",
        "X-Requested-With",
        "Sec-WebSocket-Key",
        "Sec-WebSocket-Version",
        "Sec-WebSocket-Extensions",
        "Sec-WebSocket-Protocol"
    ],
)

@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Lyria - Serviço de Transcrição",
        "endpoints": {
            "websocket": "/ws",
            "config": "/config",
            "health": "/health"
        }
    }

@app.get("/config")
async def get_config():
    return {
        "websocket_url": WEBSOCKET_URL,
        "status": "online"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "api_back_configured": API_BACK is not None
    }

@app.get("/test-tts")
async def test_tts(text: str = "Olá, este é um teste de síntese de voz"):
    logger.info(f"🧪 Teste TTS: {text}")
    audio_bytes = processador_audio.synthesize_text_to_speech(text)
    
    if audio_bytes:
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=teste.mp3"}
        )
    else:
        return JSONResponse({"error": "Falha ao gerar áudio"}, status_code=500)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("✅ Conexão WebSocket aceita")
    
    reconhecedor_voz = processador_audio.create_recognizer()
    audio_buffer = b""
    MIN_BUFFER_SIZE = 8192  

    try:
        while True:
            audio_data = await websocket.receive_bytes()
            logger.info(f"📥 Chunk: {len(audio_data)} bytes")
            
            audio_buffer += audio_data
            
            if len(audio_buffer) >= MIN_BUFFER_SIZE:
                logger.info(f"🎤 Processando {len(audio_buffer)} bytes acumulados")
                
                try:
                    transcricao = processador_audio.transcribe_audio(
                        reconhecedor_voz, 
                        audio_buffer
                    )
                    
                    if transcricao:
                        logger.info(f"📝 TRANSCRIÇÃO: '{transcricao}'")
                        
                        if not API_BACK:
                            resposta_texto = "Erro: API backend não configurada."
                        else:
                            try:
                                logger.info(f"🤖 Chamando IA...")
                                response_ai = requests.post(
                                    f"{API_BACK}/Lyria/conversar",
                                    json={"pergunta": transcricao, "persona": "social"},
                                    timeout=30
                                )
                                response_ai.raise_for_status()
                                resposta_texto = response_ai.json().get(
                                    "resposta", 
                                    "Desculpe, não entendi."
                                )
                                logger.info(f"💬 IA: {resposta_texto[:80]}...")
                                
                            except Exception as e:
                                logger.error(f"❌ Erro IA: {e}")
                                resposta_texto = "Desculpe, erro ao conectar com a IA."
                        
                        logger.info("🔊 Gerando áudio...")
                        audio_bytes = processador_audio.synthesize_text_to_speech(resposta_texto)
                        
                        if audio_bytes:
                            logger.info(f"📤 Enviando {len(audio_bytes)} bytes de áudio")
                            await websocket.send_bytes(audio_bytes)
                            logger.info("✅ Áudio enviado!")
                        else:
                            logger.error("❌ Falha ao gerar áudio")
                            await websocket.send_json({
                                "error": "Falha ao gerar áudio",
                                "text": resposta_texto
                            })
                    
                    audio_buffer = b""
                    
                except Exception as e:
                    logger.error(f"❌ Erro processamento: {e}", exc_info=True)
                    audio_buffer = b""
                    
    except WebSocketDisconnect:
        logger.info("🔌 Cliente desconectado")
    except Exception as e:
        logger.error(f"❌ Erro WebSocket: {e}", exc_info=True)
    finally:
        logger.info("🔚 Conexão encerrada")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Iniciando servidor na porta {port}")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info"
    )