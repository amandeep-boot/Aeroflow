import os
import sys
import time

try:
    from groq import Groq
except ImportError:
    print("❌ 'groq' package not installed.")
    print("Please run: python -m pip install groq")
    sys.exit(1)


def test_transcription(audio_file="test_recording.wav"):
    if not os.path.exists(audio_file):
        print(f"❌ Error: '{audio_file}' not found. Please run 'python test_audio.py' first.")
        return

    # Check for API key in environment or .env file
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key and os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if line.startswith("GROQ_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not api_key:
        api_key = input("Enter your Groq API key (starts with gsk_...): ").strip()
        if not api_key:
            print("❌ Groq API key is required.")
            return

    client = Groq(api_key=api_key)

    print(f"📡 Sending '{audio_file}' to Groq Whisper API (model: whisper-large-v3-turbo)...")
    start_time = time.perf_counter()

    try:
        with open(audio_file, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(audio_file, f.read()),
                model="whisper-large-v3-turbo",
                response_format="verbose_json",
                temperature=0.0,
            )
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        print("\n" + "=" * 45)
        print("📝 Transcription Result:")
        print(f"\"{transcription.text}\"")
        print("=" * 45)
        print(f"⚡ Latency: {elapsed_ms:.1f} ms ({elapsed_ms/1000:.2f} seconds)")

        if hasattr(transcription, "language"):
            print(f"🌐 Detected Language: {transcription.language}")

        print("\n🎉 Step 2 Succeeded! Speech-to-text is working.")

    except Exception as e:
        print(f"\n❌ API Error: {e}")


if __name__ == "__main__":
    test_transcription()
