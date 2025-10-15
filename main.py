from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from processa_audio import ProcessaAudio 
import os
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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("✅ Conexão WebSocket aceita")
    
    reconhecedor_voz = processador_audio.create_recognizer()
    audio_buffer = b""  # Buffer para acumular chunks de áudio
    
    try:
        while True:
            audio_data = await websocket.receive_bytes()
            logger.info(f"📥 Recebido chunk: {len(audio_data)} bytes")
            
            audio_buffer += audio_data
            
            if len(audio_buffer) >= 4096:
                logger.info(f"🎤 Processando buffer de {len(audio_buffer)} bytes")
                
                try:
                    transcricao = processador_audio.transcribe_audio(
                        reconhecedor_voz, 
                        audio_buffer
                    )
                    
                    if transcricao:
                        logger.info(f"📝 Transcrição: '{transcricao}'")
                        
                        if not API_BACK:
                            logger.error("❌ API_do_BACK não configurada")
                            resposta_texto = "Erro: API do backend não configurada."
                        else:
                            try:
                                logger.info(f"🤖 Enviando para IA: {API_BACK}/Lyria/conversar")
                                response_ai = requests.post(
                                    f"{API_BACK}/Lyria/conversar",
                                    json={
                                        "pergunta": transcricao,
                                        "persona": "professora"  # ✅ Adicionar persona padrão
                                    },
                                    timeout=30
                                )
                                response_ai.raise_for_status()
                                resposta_texto = response_ai.json().get(
                                    "resposta", 
                                    "Desculpe, não consegui entender."
                                )
                                logger.info(f"💬 Resposta IA: {resposta_texto[:100]}...")
                                
                            except requests.exceptions.Timeout:
                                logger.error("❌ Timeout na conexão com IA")
                                resposta_texto = "Desculpe, a resposta está demorando muito."
                            except requests.exceptions.RequestException as e:
                                logger.error(f"❌ Erro na IA: {e}")
                                resposta_texto = "Desculpe, não consegui me conectar com a IA."
                        
                        logger.info("🔊 Sintetizando voz...")
                        audio_bytes = processador_audio.synthesize_text_to_speech(resposta_texto)
                        
                        if audio_bytes:
                            logger.info(f"📤 Enviando áudio: {len(audio_bytes)} bytes")
                            await websocket.send_bytes(audio_bytes)
                        else:
                            logger.error("❌ Falha ao sintetizar áudio")
                            await websocket.send_json({
                                "error": "Falha ao gerar áudio",
                                "text": resposta_texto
                            })
                    else:
                        logger.debug("⏳ Transcrição parcial ou vazia")
                    
                    audio_buffer = b""
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao processar áudio: {e}", exc_info=True)
                    audio_buffer = b""  # Limpar buffer em caso de erro
                    
    except WebSocketDisconnect:
        logger.info("🔌 Cliente desconectado normalmente")
    except Exception as e:
        logger.error(f"❌ Erro crítico na conexão WebSocket: {e}", exc_info=True)
    finally:
        logger.info("🔚 Encerrando conexão WebSocket")

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
