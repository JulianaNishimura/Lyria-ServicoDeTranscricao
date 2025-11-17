from vosk import Model, KaldiRecognizer
import json
import wave
import io

class ProcessaAudio:
    def __init__(self):
        self.modelo = Model(os.getenv("MODEL_PATH"))

    def criar_reconhecedor(self):
        return KaldiRecognizer(self.modelo, 16000)

    def transcrever(self, reconhecedor, audio_bytes):
        wf = wave.open(io.BytesIO(audio_bytes), "rb")
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            reconhecedor.AcceptWaveform(data)
        resultado = reconhecedor.FinalResult()
        return json.loads(resultado).get("text", "")
