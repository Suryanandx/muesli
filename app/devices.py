"""List available audio input devices. Run: python -m app.devices"""
from app.audio import AudioRecorder

if __name__ == "__main__":
    devices = AudioRecorder.list_devices()
    print("\nAvailable audio input devices:\n")
    for d in devices:
        print(f"  [{d['id']}] {d['name']}  ({d['channels']} ch)")
    print("\nSet AUDIO_DEVICE=<name> in your .env to use a specific device.")
    print("To capture system audio on macOS, install BlackHole:")
    print("  brew install blackhole-2ch")
    print("  Then set AUDIO_DEVICE=BlackHole 2ch\n")
