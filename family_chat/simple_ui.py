"""
Simple transcription UI - minimal mode without AI tools.
Clean, continuous terminal output for demos and basic transcription.
"""

import sys
import json
import threading
from typing import Optional

from websockets import ConnectionClosedOK
from websockets.sync.client import connect
import pyaudio  # type: ignore

from .session import Session, resolve_language
from .transcription import (
    SONIOX_WEBSOCKET_URL,
    SAMPLE_RATE,
    NUM_CHANNELS,
    CHUNK_SIZE,
    get_soniox_config,
)

# Speaker colors (ANSI)
SPEAKER_COLORS = [
    "\033[92m",  # bright green
    "\033[96m",  # bright cyan
    "\033[95m",  # bright magenta
    "\033[93m",  # bright yellow
    "\033[94m",  # bright blue
    "\033[91m",  # bright red
]

# Language flags
# TODO: Language generalization - Add more language flags (see ui.py TODO).
LANGUAGE_FLAGS = {
    "en": "🇺🇸",
    "zh": "🇨🇳",
    "he": "🇮🇱",
    "ca": "🇪🇸",
}

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"


def get_speaker_color(speaker_id: int | str) -> str:
    """Get unique color for speaker."""
    sid = int(speaker_id) if isinstance(speaker_id, str) else speaker_id
    return SPEAKER_COLORS[sid % len(SPEAKER_COLORS)]


def get_language_flag(language: str) -> str:
    """Get flag emoji for language."""
    return LANGUAGE_FLAGS.get(language, "🌐")


def run_simple_transcription(
    api_key: str,
    session: Session,
    context: Optional[str] = None,
    device_index: Optional[int] = None,
) -> None:
    """Run simple transcription - continuous terminal output."""
    
    # Initialize audio
    audio = pyaudio.PyAudio()
    device_idx = None
    device_name = "Unknown"
    
    # If a specific device was requested, use it
    if device_index is not None:
        try:
            info = audio.get_device_info_by_index(device_index)
            if info.get("maxInputChannels", 0) > 0:
                device_idx = device_index
                device_name = str(info.get("name", "Unknown"))
        except Exception:
            print(f"{SPEAKER_COLORS[5]}Device {device_index} not found.{RESET}")
            audio.terminate()
            return
    else:
        # Collect all input devices
        input_devices: list[tuple[int, dict]] = []
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                input_devices.append((i, info))
        
        # Prefer MacBook's built-in microphone (more reliable than Bluetooth/virtual)
        for idx, info in input_devices:
            name = str(info.get("name", "")).lower()
            if "macbook" in name and "microphone" in name:
                device_idx = idx
                device_name = str(info.get("name", "Unknown"))
                break
        
        # Fall back to system default
        if device_idx is None:
            try:
                default_info = audio.get_default_input_device_info()
                default_name = default_info.get("name")
                for idx, info in input_devices:
                    if info.get("name") == default_name:
                        device_idx = idx
                        device_name = str(info.get("name", "Unknown"))
                        break
            except Exception:
                pass
        
        # Last resort: first available input device
        if device_idx is None and input_devices:
            idx, info = input_devices[0]
            device_idx = idx
            device_name = str(info.get("name", "Unknown"))
    
    if device_idx is None:
        print(f"{SPEAKER_COLORS[5]}No microphone found.{RESET}")
        audio.terminate()
        return
    
    # Print header
    print(f"\n{BOLD}🎙 Live Transcription{RESET}")
    print(f"{DIM}{'─' * 50}{RESET}")
    print(f"\033[92m✓{RESET} Mic: {device_name}")
    print(f"\033[92m✓{RESET} Session: {session.name}")
    
    if session.was_resumed:
        info = session.get_resume_info()
        if info:
            print(f"\033[93m📂 Resuming: {info['token_count']} tokens{RESET}")
    
    print(f"{DIM}{'─' * 50}{RESET}")
    print(f"{DIM}Ctrl+C to stop and save{RESET}\n")
    
    # Open audio stream
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=NUM_CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        input_device_index=device_idx,
        frames_per_buffer=CHUNK_SIZE
    )
    
    running = threading.Event()
    running.set()
    
    # State for continuous output
    current_speaker: Optional[int | str] = None
    current_language: Optional[str] = None
    current_is_translation: bool = False
    current_color: str = RESET
    pending_text: str = ""  # Non-final text we've shown (need to overwrite)
    
    def stream_mic(ws) -> None:
        """Stream microphone audio to websocket."""
        try:
            while running.is_set():
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                session.add_audio_frame(data)
                ws.send(data)
        except Exception:
            pass
        try:
            ws.send("")
        except Exception:
            pass
    
    print(f"{DIM}Connecting...{RESET}")
    
    try:
        config = get_soniox_config(api_key, context)
        
        with connect(SONIOX_WEBSOCKET_URL) as ws:
            ws.send(json.dumps(config))
            
            # Start mic streaming
            mic_thread = threading.Thread(target=stream_mic, args=(ws,), daemon=True)
            mic_thread.start()
            
            print(f"\033[92mListening...{RESET}\n")
            
            try:
                while running.is_set():
                    message = ws.recv()
                    res = json.loads(message)
                    
                    if res.get("error_code") is not None:
                        print(f"\n{SPEAKER_COLORS[5]}Error: {res['error_code']} - {res.get('error_message')}{RESET}")
                        break
                    
                    # Process tokens
                    for token in res.get("tokens", []):
                        text = token.get("text", "")
                        if not text:
                            continue
                        
                        speaker = token.get("speaker")
                        language = token.get("language")
                        is_translation = token.get("translation_status") == "translation"
                        is_final = token.get("is_final", False)
                        source_lang = token.get("source_language")
                        
                        # Resolve language
                        resolved_lang = resolve_language(token, session)
                        token["resolved_language"] = resolved_lang
                        
                        # Skip translations of English content
                        if is_translation and source_lang == "en":
                            continue
                        
                        # Clear pending non-final text if we have new content
                        if pending_text:
                            # Move cursor back and clear
                            sys.stdout.write(f"\r\033[K")
                            sys.stdout.write("\033[A" * pending_text.count("\n"))
                            sys.stdout.write(f"\r\033[K")
                            pending_text = ""
                        
                        output = ""
                        
                        # Speaker changed - new paragraph
                        if speaker is not None and speaker != current_speaker:
                            if current_speaker is not None:
                                output += f"{RESET}\n\n"
                            current_speaker = speaker
                            current_language = language
                            current_is_translation = False
                            profile = session.get_speaker_profile(speaker)
                            
                            current_color = get_speaker_color(speaker)
                            flag = get_language_flag(language) if language else ""
                            output += f"{current_color}{BOLD}{profile.get_label()}: {flag}{RESET}{current_color} "
                            text = text.lstrip()
                        
                        # Translation line - indent
                        if is_translation and not current_is_translation:
                            current_is_translation = True
                            flag = get_language_flag(language) if language else ""
                            output += f"\n  ↳ {flag} {ITALIC}"
                            text = text.lstrip()
                        elif not is_translation and current_is_translation:
                            # Back from translation
                            current_is_translation = False
                            flag = get_language_flag(language) if language else ""
                            output += f"\n{flag} "
                            text = text.lstrip()
                        
                        # Add the text
                        if is_final:
                            session.add_token(token)
                            output += text
                            sys.stdout.write(output)
                            sys.stdout.flush()
                        else:
                            # Non-final: show dimmed, will be overwritten
                            output += f"{DIM}{text}{RESET}{current_color}"
                            sys.stdout.write(output)
                            sys.stdout.flush()
                            pending_text = output
                    
                    if res.get("finished"):
                        break
                        
            except ConnectionClosedOK:
                pass
            except KeyboardInterrupt:
                print(f"\n\n{RESET}\033[93mStopping...{RESET}")
    
    except Exception as e:
        print(f"{SPEAKER_COLORS[5]}Error: {e}{RESET}")
    
    finally:
        running.clear()
        stream.stop_stream()
        stream.close()
        audio.terminate()
        
        # Save
        print(f"{RESET}")
        if session.final_tokens:
            path = session.save_segment()
            print(f"\033[92m✓{RESET} Saved: {path}")
        else:
            print(f"{DIM}No transcript to save.{RESET}")
