import os

from app.services.voice_synthesis import ElevenLabsClient


def main() -> None:
    """Simple smoke test for ElevenLabs integration.

    Reads ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID from environment,
    synthesizes a short sentence, and writes test_elevenlabs.mp3.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "yD0Zg2jxgfQLY8I2MEHO")

    if not api_key:
        print("❌ ELEVENLABS_API_KEY is not set in the environment.")
        print("   Set it, then re-run: python test_elevenlabs_client.py")
        return

    client = ElevenLabsClient(api_key=api_key, voice_id=voice_id)

    text = "The first move is what sets everything in motion."
    print(f"🔊 Requesting ElevenLabs audio for: {text!r}")

    result = client.synthesize(text=text, language="en")

    output_file = "test_elevenlabs.mp3"
    with open(output_file, "wb") as f:
        f.write(result.audio_bytes)

    print(f"✅ Wrote {len(result.audio_bytes)} bytes to {output_file}")
    print("   Open this file in any media player to verify the audio.")


if __name__ == "__main__":
    main()


