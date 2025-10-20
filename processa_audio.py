import os
import json
import io
import logging
from vosk import Model, KaldiRecognizer
from gtts import gTTS

logger = logging.getLogger(__name__)

MODEL_PATH = "vosk-model-small-pt-0.3"

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Modelo Vosk não encontrado em {MODEL_PATH}.")

class ProcessaAudio:
    def __init__(self, sample_rate=16000):
        logger.info(f"🎵 Inicializando ProcessaAudio (sample_rate={sample_rate})")
        self.model = Model(MODEL_PATH)
        self.sample_rate = sample_rate
        self.frame_count = 0
        logger.info("✅ Modelo Vosk carregado com sucesso")
    
    def create_recognizer(self):
        """Cria um novo reconhecedor Vosk"""
        recognizer = KaldiRecognizer(self.model, self.sample_rate)
        recognizer.SetWords(True)  # Ativar detecção de palavras individuais
        return recognizer
    
    def transcribe_audio(self, recognizer, audio_data: bytes):
        """
        Transcreve áudio PCM 16-bit mono
        ✅ Aceita apenas dados RAW (não WebM)
        """
        try:
            self.frame_count += 1
            data_size = len(audio_data)
            logger.info(f"🎤 Frame {self.frame_count}: {data_size} bytes")
            
            # ✅ Processar com Vosk diretamente
            if recognizer.AcceptWaveform(audio_data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                
                if text:
                    logger.info(f"✅ TRANSCRIÇÃO COMPLETA: '{text}'")
                    self.frame_count = 0  # Reset contador
                    return text
                else:
                    logger.debug("⏳ Silêncio detectado")
                    return None
            else:
                # Resultado parcial (ainda processando)
                partial = json.loads(recognizer.PartialResult())
                partial_text = partial.get("partial", "").strip()
                if partial_text:
                    logger.debug(f"⏳ Parcial: '{partial_text}'")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro na transcrição: {e}", exc_info=True)
            return None
    
    def synthesize_text_to_speech(self, text: str):
        """
        Sintetiza texto em áudio MP3 usando Google TTS
        """
        try:
            logger.info(f"🔊 Sintetizando: '{text[:80]}...'")
            
            if not text or text.strip() == "":
                logger.warning("⚠️ Texto vazio")
                return None
            
            # Gerar áudio
            tts = gTTS(text=text, lang='pt', slow=False)
            audio_stream = io.BytesIO()
            tts.write_to_fp(audio_stream)
            audio_stream.seek(0)
            
            audio_bytes = audio_stream.getvalue()
            logger.info(f"✅ Áudio sintetizado: {len(audio_bytes)} bytes (MP3)")
            
            return audio_bytes
            
        except Exception as e:
            logger.error(f"❌ Erro na síntese: {e}", exc_info=True)
            return None