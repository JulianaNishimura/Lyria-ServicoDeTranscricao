import io
import json
import logging
from vosk import Model, KaldiRecognizer
from gtts import gTTS
from pydub import AudioSegment

logger = logging.getLogger(__name__)

class ProcessaAudio:
    def __init__(self, model_path="./vosk-model-small-pt-0.3"):
        self.model = Model(model_path)
        self.sample_rate = 16000

    def criar_reconhecedor(self):
        rec = KaldiRecognizer(self.model, self.sample_rate)
        rec.SetWords(True)
        return rec

    def transcrever(self, reconhecedor, webm_data: bytes):
        try:
            audio = AudioSegment.from_file(io.BytesIO(webm_data), format="webm")
            audio = audio.set_frame_rate(self.sample_rate).set_channels(1)
            pcm = audio.raw_data
            if reconhecedor.AcceptWaveform(pcm):
                resultado = json.loads(reconhecedor.Result())
                return resultado.get("text", "").strip()
        except Exception as e:
            logger.error(f"Erro na transcrição: {e}")
        return None

    def texto_para_audio(self, texto: str) -> bytes:
        tts = gTTS(text=texto or "Desculpe, não entendi.", lang='pt', slow=False)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        return buffer.getvalue()