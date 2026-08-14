#!/usr/bin/env python3
"""Transcribe audio and generate AI summary with Ollama."""
import sys
import requests
from faster_whisper import WhisperModel

def transcribe_and_summarize(audio_path):
    # Step 1: Transcribe
    print("Transcribing...")
    model = WhisperModel("large-v3", device="auto", compute_type="int8")
    segments, info = model.transcribe(audio_path, beam_size=5, vad_filter=True)

    transcript = ""
    for seg in segments:
        mins = int(seg.start // 60)
        secs = int(seg.start % 60)
        transcript += f"[{mins:02d}:{secs:02d}] {seg.text.strip()}\n"

    print(f"Transcribed {info.duration:.0f}s of {info.language} audio")

    # Step 2: Summarize with Ollama
    print("Generating summary...")
    prompt = f"""Analyze this transcript and provide:
1. A 3-sentence summary
2. Key topics discussed (bullet points)
3. Action items mentioned (if any)
4. Notable quotes

Transcript:
{transcript[:8000]}"""  # Trim to fit context window

    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "llama3.2",
        "prompt": prompt,
        "stream": False
    })

    summary = response.json()["response"]

    # Save both outputs
    with open(audio_path.rsplit(".", 1)[0] + "_transcript.txt", "w") as f:
        f.write(transcript)
    with open(audio_path.rsplit(".", 1)[0] + "_summary.md", "w") as f:
        f.write(summary)

    print(f"\nSummary:\n{summary}")

if __name__ == "__main__":
    transcribe_and_summarize(sys.argv[1])


# # Cron job: auto-transcribe any new files in ~/Recordings
# # Add to crontab -e:
# */5 * * * * find ~/Recordings -name "*.mp3" -newer ~/Recordings/.last_processed -exec python3 ~/transcribe_summarize.py {} \; && touch ~/Recordings/.last_processed
