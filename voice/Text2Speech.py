import requests
import subprocess


KOKORO_URL = "http://localhost:8880"
output_audio_file = "resources/audio/Output/output.wav"

def speak(text):

    response = requests.post(
        f"{KOKORO_URL}/v1/audio/speech",
        json={
            "input": text,
            "voice": "af_bella",
            "response_format": "wav"
        }
    )

    with open(output_audio_file, "wb") as f:
        f.write(response.content)

    return output_audio_file

def play_audio(file):

    subprocess.run(
        [
            "aplay",
            file
        ]
    )