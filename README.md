# Mother-in-Law Decoder

Real-time transcription and translation for multilingual family conversations. Know what everyone in your wife's family is saying. This does not currently decode subtle hints and other common in-laws language tactics.

## The Problem

Your in-laws speak a language you don't. You catch your name in the middle of a confusing sentence, and hope they don't think you're an idiot.

## The Solution

Pull up the computer during the the conversation. Get live transcription and translation to the language of your choice in your terminal (English by default). You can also label the speakers later on.

## Quick Start

```bash
# Setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
echo "SONIOX_API_KEY=your_key" > .env  # Get one at soniox.com

# Run
python live-transcription.py --session "xmas dinner"
```

## Usage

```bash
# Add context for better accuracy
python main.py --session "xmas dinner" --context "Family discussing vacation plans"
```

**Controls:** `v` to scroll history, `q` to quit and save.

## Selecting a Microphone

By default, the app auto-selects your MacBook's built-in microphone. To use a different device:

1. **List available devices:**
   ```bash
   python main.py --list-devices
   ```
   Output:
   ```
   Available audio input devices:
     [0] MacBook Pro Microphone (default)
     [1] USB Audio Device
     [2] AirPods Pro
   ```

2. **Run with your chosen device:**
   ```bash
   python main.py --session "xmas dinner" --device 1
   ```

### No Audio? Debug It

If transcription shows "Waiting for speech..." but you're talking:

```bash
python debug_mic.py
```

This tests your microphone directly and shows a live audio level meter. Common fixes:
- **Permission denied:** System Settings → Privacy & Security → Microphone
- **Wrong device:** Try a different `--device` index
- **Muted mic:** Check system audio settings

## Output

Transcripts save to `output/<session>/` as JSON, TXT, and MP3. Resume anytime with the same session name.

## Requirements

- Python 3.10+
- [Soniox API key](https://soniox.com)

## Supported Languages

🇸🇦 Arabic, 🪨 Basque, 🇧🇦 Bosnian, 🇧🇬 Bulgarian, 🐈 Catalan, 🇨🇳 Chinese, 🇭🇷 Croatian, 🇨🇿 Czech, 🇩🇰 Danish, 🇳🇱 Dutch, 🇺🇸 English, 🇪🇪 Estonian, 🇫🇮 Finnish, 🇫🇷 French, 🐟 Galician, 🇩🇪 German, 🇬🇷 Greek, 🇮🇳 Gujarati, 🇮🇱 Hebrew, 🇮🇳 Hindi, 🇭🇺 Hungarian, 🇮🇩 Indonesian, 🇮🇹 Italian, 🇯🇵 Japanese, 🇰🇷 Korean, 🇱🇻 Latvian, 🇱🇹 Lithuanian, 🇲🇰 Macedonian, 🇲🇾 Malay, 🇮🇳 Malayalam, 🇮🇳 Marathi, 🇳🇴 Norwegian, 🇮🇷 Persian, 🇵🇱 Polish, 🇵🇹 Portuguese, 🇮🇳 Punjabi, 🇷🇴 Romanian, 🇷🇺 Russian, 🇷🇸 Serbian, 🇸🇰 Slovak, 🇸🇮 Slovenian, 🇪🇸 Spanish, 🇸🇪 Swedish, 🇵🇭 Tagalog, 🇮🇳 Tamil, 🇮🇳 Telugu, 🇹🇭 Thai, 🇹🇷 Turkish, 🇺🇦 Ukrainian, 🇵🇰 Urdu, 🇻🇳 Vietnamese

---

MIT License
