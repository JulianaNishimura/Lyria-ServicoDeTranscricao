import os
import json
import io
from vosk import Model, KaldiRecognizer
from gtts import gTTS

MODEL_PATH = "vosk-model-small-pt-0.3"

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError("Modelo Vosk não encontrado. Por favor, baixe-o e descompacte.")

class ProcessaAudio:
    def __init__(self, sample_rate=16000):
        self.model = Model(MODEL_PATH)
        self.sample_rate = sample_rate

    def create_recognizer(self):
        return KaldiRecognizer(self.model, self.sample_rate)

    def transcribe_audio(self, recognizer, audio_data: bytes):
        if recognizer.AcceptWaveform(audio_data):
            result = json.loads(recognizer.Result())
            return result.get("text", "")
        return None
    
    def synthesize_text_to_speech(self, text: str):
        try:
            tts = gTTS(text=text, lang='pt')
            audio_stream = io.BytesIO()
            tts.write_to_fp(audio_stream)
            audio_stream.seek(0)
            return audio_stream.getvalue()
        except Exception as e:
            print(f"Erro na síntese de voz: {e}")
            return None