import sys
import time
import wave
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("❌ 'sounddevice' or 'numpy' is not installed yet.")
    print("Please run: python -m pip install sounddevice numpy")
    sys.exit(1)


def list_audio_devices():
    print("\n--- Available Audio Input Devices ---")
    devices = sd.query_devices()
    default_input = sd.default.device[0]
    input_indices = []

    for idx, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            input_indices.append(idx)
            marker = "👉 [DEFAULT]" if idx == default_input else "   "
            hostapi = sd.query_hostapis(dev["hostapi"])["name"]
            print(f"{marker} [{idx}] {dev['name']} ({hostapi})")
    print("-------------------------------------\n")
    return default_input, input_indices


def test_microphone(device_idx=None, duration_sec=4, sample_rate=16000):
    dev_info = sd.query_devices(device_idx)
    print(f"\n🎙️  Recording using device [{device_idx}]: '{dev_info['name']}'")
    print(f"⏱️  Duration: {duration_sec}s | Sample Rate: {sample_rate}Hz (mono)")
    print("Speak clearly into your microphone now!\n")

    recorded_chunks = []
    block_size = int(sample_rate * 0.1)  # 100ms blocks

    def callback(indata, frames, time_info, status):
        if status:
            print(f"\n[Warning: {status}]", file=sys.stderr)
        recorded_chunks.append(indata.copy())

        peak = float(np.max(np.abs(indata)))
        rms = float(np.sqrt(np.mean(indata**2)))
        
        # Visual meter (scaled for speech)
        bar_len = int(min(peak * 50, 30))
        meter = "█" * bar_len + "░" * (30 - bar_len)
        print(f"\rLevel: [{meter}] Peak: {peak:0.2f} RMS: {rms:0.3f} ", end="", flush=True)

    with sd.InputStream(
        device=device_idx,
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        blocksize=block_size,
        callback=callback,
    ):
        time.sleep(duration_sec)

    print("\n\n✅ Recording finished!")

    if not recorded_chunks:
        print("❌ No audio captured!")
        return

    full_audio = np.concatenate(recorded_chunks, axis=0)
    max_peak = float(np.max(np.abs(full_audio)))
    avg_rms = float(np.sqrt(np.mean(full_audio**2)))

    print(f"\n📊 Sound Analysis:")
    print(f"   Max Peak: {max_peak:.4f}")
    print(f"   Avg RMS:  {avg_rms:.4f}")

    if max_peak < 0.05:
        print("\n⚠️  Low Volume: Very little sound was detected.")
        print("   Tips:")
        print("   - Check Windows Sound Settings > Input Volume")
        print("   - Ensure your headset mic is not muted")
        print("   - Try selecting a different device index from the list")
    else:
        print("\n🎉 Excellent! Clear audio signal detected.")

    wav_filename = "test_recording.wav"
    audio_int16 = (full_audio * 32767).astype(np.int16)
    with wave.open(wav_filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())
    print(f"💾 Saved audio to '{wav_filename}'")


if __name__ == "__main__":
    default_dev, valid_indices = list_audio_devices()
    user_choice = input(f"Enter device number to test (or press Enter for default [{default_dev}]): ").strip()
    
    if user_choice.isdigit() and int(user_choice) in valid_indices:
        chosen_device = int(user_choice)
    else:
        chosen_device = default_dev

    test_microphone(device_idx=chosen_device, duration_sec=4)
