# 🎙️ Mother-in-Law Decoder

**Ever sit through hours of family dinner catching only your name and random words you vaguely recognize?** Yeah, me too.

My wife speaks Bulgarian with her mom. I... don't. This tool helps.

## What It Does

Real-time transcription + translation of family conversations, so you can:
- Actually know what everyone's talking about
- Stop pretending to laugh at jokes you didn't understand
- Scroll through the full conversation history
- Prove your mother-in-law *was* talking about you

Built with [Soniox](https://soniox.com) for transcription.

## Quick Start

```bash
# Install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup API key (get it from Soniox)
echo "SONIOX_API_KEY=your_key_here" > .env

# Run it (simple mode - continuous output)
python live-transcription.py --session "dinner-with-in-laws" --minimal

# Or run it with interactive UI and scroll mode
python live-transcription.py --session "sunday-lunch"
```

## Features

### 🎯 Simple Mode (`--minimal`)
Perfect for just following along:
- Real-time transcription with speaker identification
- Live translation to English (or your language of choice)
- Color-coded speakers so you know who's saying what
- Continuous output that scrolls in your terminal
- Save transcripts for later (or for evidence)

### 🖥️ Interactive Mode (default)
Full UI with scroll capability:
- Real-time transcription with speaker identification
- Live translation to English (or your language of choice)
- Color-coded speakers so you know who's saying what
- Save transcripts for later (or for evidence)

| Hotkey | What It Does |
|--------|-------------|
| `v` | Scroll through full conversation history |
| `q` | Quit and save |

**Scroll mode navigation:**
- `j`/`k` or `↑`/`↓` - Scroll up/down
- `g`/`G` - Jump to top/bottom
- `q` - Exit scroll mode

### 🌍 Language Support

Currently configured for a few languages, but Soniox supports way more:
- English ↔ anything
- Bulgarian, Chinese, Hebrew, Spanish, French, Russian, and many more

*(There are TODOs in the code to make this fully configurable - PRs welcome!)*

## The Origin Story

**Me:** *sits at Bulgarian family dinner*
**Mother-in-law:** *[20 minutes of animated Bulgarian]*
**Me:** *catches the word "work" and my name*
**Me:** *nervous laughter*
**Wife:** "She was asking if you want more potatoes."

Never again.

## How It Works

1. **Microphone** → captures everyone talking
2. **Soniox Live API** → transcribes + translates in real-time
3. **Your terminal** → shows everything as it happens

Everything is saved locally. The only network calls are to Soniox.

## Configuration

```bash
# List your audio devices
python live-transcription.py --list-devices

# Use specific microphone
python live-transcription.py --session "test" --device 2

# Provide context for better accuracy
python live-transcription.py --session "dinner" \
  --context "Family dinner conversation about work and vacation plans"
```

## Output

Transcripts are saved to `family-conversations/session-name/`:
```
family-conversations/
  └── sunday-lunch/
      ├── session_state.json          # Resume later
      ├── segment_001_20251222.json   # Full data
      ├── segment_001_20251222.txt    # Human-readable transcript
      └── segment_001_20251222.mp3    # Audio recording
```

**Resume a conversation** by using the same session name:
```bash
python live-transcription.py --session "sunday-lunch"
# Picks up where you left off!
```

## Tech Stack

- **Soniox** - Best-in-class multilingual transcription + translation
- **Rich** - Pretty terminal UI
- **Python** - Because it's 2025 and we still love Python

## Limitations & TODOs

- Currently hardcoded for certain language pairs (see `# TODO` comments in code)
- Target translation language is hardcoded to English (fixable with ~10 lines)
- Doesn't work offline (requires Soniox API)
- Won't help you understand inside jokes (that's on you)

## Contributing

Found a bug? Want to add your language? PRs welcome!

Key areas marked with `# TODO: Language generalization` in:
- `family_chat/transcription.py` - Language hints and translation targets
- `family_chat/session.py` - Speaker language detection logic

## Troubleshooting

**Microphone not working?**
```bash
python debug_mic.py  # Test your microphone
python live-transcription.py --list-devices  # List available devices
```

## License

MIT - Use it, fork it, make it better.

## FAQ

**Q: Will this work for other languages besides Bulgarian?**
A: Yep! Soniox supports tons of languages. See the TODOs in the code for customization.

**Q: Can I change the target translation language?**
A: Not yet (it's hardcoded to English), but there's a TODO for it. Should be easy.

**Q: Is this actually useful or just a fun project?**
A: Yes.

**Q: Does your mother-in-law know about this?**
A: She does now.

---

Made with ❤️ (and confusion) by someone who really should learn Bulgarian.

*P.S. - If you're also married to someone with a foreign-language family, you're welcome.*
