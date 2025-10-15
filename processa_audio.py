import os
import json
import io
import logging
from vosk import Model, KaldiRecognizer
from gtts import gTTS
from pydub import AudioSegment

logger = logging.getLogger(__name__)

MODEL_PATH = "vosk-model-small-pt-0.3"

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Modelo Vosk não encontrado em {MODEL_PATH}. Por favor, baixe-o e descompacte.")

class ProcessaAudio:
    def __init__(self, sample_rate=16000):
        logger.info(f"🎵 Inicializando ProcessaAudio com sample_rate={sample_rate}")
        self.model = Model(MODEL_PATH)
        self.sample_rate = sample_rate
        logger.info("✅ Modelo Vosk carregado com sucesso")
    
    def create_recognizer(self):
        """Cria um novo reconhecedor"""
        return KaldiRecognizer(self.model, self.sample_rate)
    
    def transcribe_audio(self, recognizer, audio_data: bytes):
        """
        Transcreve áudio recebido do WebSocket
        ✅ Converte WebM para PCM antes de processar
        """
        try:
            logger.info(f"🎤 Transcrevendo {len(audio_data)} bytes de áudio")
            
            # ✅ Converter WebM para PCM 16-bit mono
            try:
                audio = AudioSegment.from_file(
                    io.BytesIO(audio_data), 
                    format="webm"
                )
                
                # Converter para o formato que o Vosk espera
                audio = audio.set_frame_rate(self.sample_rate)
                audio = audio.set_channels(1)  # Mono
                audio = audio.set_sample_width(2)  # 16-bit
                
                # Exportar como WAV raw (PCM)
                pcm_data = audio.raw_data
                logger.info(f"✅ Áudio convertido para PCM: {len(pcm_data)} bytes")
                
            except Exception as e:
                logger.warning(f"⚠️ Falha ao converter WebM, tentando usar dados diretos: {e}")
                pcm_data = audio_data
            
            # ✅ Processar com Vosk
            if recognizer.AcceptWaveform(pcm_data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                
                if text:
                    logger.info(f"✅ Transcrição completa: '{text}'")
                    return text
                else:
                    logger.warning("⚠️ Transcrição vazia")
                    return None
            else:
                # Resultado parcial
                partial = json.loads(recognizer.PartialResult())
                partial_text = partial.get("partial", "").strip()
                if partial_text:
                    logger.info(f"⏳ Transcrição parcial: '{partial_text}'")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro na transcrição: {e}", exc_info=True)
            return None
    
    def synthesize_text_to_speech(self, text: str):
        """
        Sintetiza texto em áudio usando Google TTS
        Retorna bytes de áudio MP3
        """
        try:
            logger.info(f"🔊 Sintetizando: '{text[:50]}...'")
            
            if not text or text.strip() == "":
                logger.warning("⚠️ Texto vazio para sintetizar")
                return None
            
            tts = gTTS(text=text, lang='pt', slow=False)
            audio_stream = io.BytesIO()
            tts.write_to_fp(audio_stream)
            audio_stream.seek(0)
            
            audio_bytes = audio_stream.getvalue()
            logger.info(f"✅ Áudio sintetizado: {len(audio_bytes)} bytes")
            
            return audio_bytes
            
        except Exception as e:
            logger.error(f"❌ Erro na síntese de voz: {e}", exc_info=True)
            return None
