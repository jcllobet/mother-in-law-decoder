"""
WebSocket transcription and audio capture module.
"""

import json
import threading
from typing import Optional, Callable
from queue import Queue

from websockets import ConnectionClosedOK
from websockets.sync.client import connect
import pyaudio  # type: ignore

from .session import Session, resolve_language

SONIOX_WEBSOCKET_URL = "wss://stt-rt.soniox.com/transcribe-websocket"

# Audio settings
SAMPLE_RATE = 16000
NUM_CHANNELS = 1
CHUNK_SIZE = 3200  # ~200ms at 16kHz


# TODO: Language generalization - Currently hardcoded to 4 languages.
# Soniox Live API supports many more languages (Bulgarian, Russian, Spanish, French, etc.).
# Make this user-configurable to support all available Soniox languages.
# Supported source languages (other party may speak these)
# English is always the target/output language
SUPPORTED_LANGUAGES = ["en", "zh", "he", "ca"]  # English, Chinese, Hebrew, Catalan


def get_soniox_config(
    api_key: str,
    context: Optional[str] = None,
    languages: Optional[list[str]] = None,
) -> dict:
    """Get Soniox STT config for multilingual transcription.
    
    Args:
        api_key: Soniox API key
        context: Optional context hint for better accuracy
        languages: Language hints (defaults to SUPPORTED_LANGUAGES)
    """
    lang_hints = languages or SUPPORTED_LANGUAGES
    
    config = {
        "api_key": api_key,
        "model": "stt-rt-v3",
        "audio_format": "pcm_s16le",
        "sample_rate": SAMPLE_RATE,
        "num_channels": NUM_CHANNELS,
        "language_hints": lang_hints,
        "enable_language_identification": True,
        "enable_speaker_diarization": True,
        "enable_endpoint_detection": True,
        # TODO: User-configurable target translation language.
        # Currently hardcoded to "en" (English). Should allow users to set their preferred
        # target language (e.g., "en", "es", "de", etc.) via CLI argument or config file.
        # Translate all non-English to English
        "translation": {
            "type": "one_way",
            "target_language": "en",
        },
    }
    
    if context:
        config["context"] = {"text": context}
    
    return config


def list_audio_devices() -> list[tuple[int, str]]:
    """List all available input devices. Returns list of (index, name) tuples."""
    audio = pyaudio.PyAudio()
    devices = []
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info.get("maxInputChannels", 0) > 0:
            devices.append((i, str(info.get("name", "Unknown"))))
    audio.terminate()
    return devices


class Transcriber:
    """Handles WebSocket connection and audio streaming for transcription."""
    
    def __init__(
        self,
        api_key: str,
        session: Session,
        on_tokens: Optional[Callable[[list[dict], list[dict]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_connected: Optional[Callable[[], None]] = None,
        context: Optional[str] = None,
        device_index: Optional[int] = None,
    ):
        self.api_key = api_key
        self.session = session
        self.on_tokens = on_tokens
        self.on_error = on_error
        self.on_connected = on_connected
        self.context = context
        self.device_index = device_index
        
        self._running = threading.Event()
        self._audio: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None
        self._ws = None
        self._mic_thread: Optional[threading.Thread] = None
        self._recv_thread: Optional[threading.Thread] = None
        self._device_name: Optional[str] = None
        
    @property
    def is_running(self) -> bool:
        return self._running.is_set()
    
    @property
    def device_name(self) -> Optional[str]:
        return self._device_name
    
    def _find_microphone(self) -> Optional[int]:
        """Find input device - uses specified device_index, or prefers MacBook mic."""
        self._audio = pyaudio.PyAudio()
        
        # If a specific device was requested, use it
        if self.device_index is not None:
            try:
                info = self._audio.get_device_info_by_index(self.device_index)
                if info.get("maxInputChannels", 0) > 0:
                    self._device_name = str(info.get("name", "Unknown"))
                    return self.device_index
            except Exception:
                pass
            return None
        
        # Collect all input devices
        input_devices: list[tuple[int, dict]] = []
        for i in range(self._audio.get_device_count()):
            info = self._audio.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                input_devices.append((i, info))
        
        if not input_devices:
            return None
        
        # Prefer MacBook's built-in microphone (more reliable than Bluetooth/virtual)
        for idx, info in input_devices:
            name = str(info.get("name", "")).lower()
            if "macbook" in name and "microphone" in name:
                self._device_name = str(info.get("name", "Unknown"))
                return idx
        
        # Fall back to system default
        try:
            default_info = self._audio.get_default_input_device_info()
            default_name = default_info.get("name")
            for idx, info in input_devices:
                if info.get("name") == default_name:
                    self._device_name = str(info.get("name", "Unknown"))
                    return idx
        except Exception:
            pass
        
        # Last resort: first available input device
        idx, info = input_devices[0]
        self._device_name = str(info.get("name", "Unknown"))
        return idx
    
    def _stream_microphone(self) -> None:
        """Capture audio from microphone and send to websocket."""
        try:
            while self._running.is_set() and self._stream and self._ws:
                data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                self.session.add_audio_frame(data)
                self._ws.send(data)
        except Exception:
            pass
        
        # Signal end-of-audio
        try:
            if self._ws:
                self._ws.send("")
        except Exception:
            pass
    
    def _receive_messages(self) -> None:
        """Receive and process messages from websocket."""
        try:
            while self._running.is_set() and self._ws:
                message = self._ws.recv()
                res = json.loads(message)
                
                # Error from server
                if res.get("error_code") is not None:
                    if self.on_error:
                        self.on_error(f"{res['error_code']} - {res.get('error_message', 'Unknown error')}")
                    break
                
                # Parse tokens
                final_tokens: list[dict] = []
                non_final_tokens: list[dict] = []
                
                for token in res.get("tokens", []):
                    if token.get("text"):
                        # Resolve language using speaker history
                        resolved_lang = resolve_language(token, self.session)
                        token["resolved_language"] = resolved_lang
                        
                        if token.get("is_final"):
                            self.session.add_token(token)
                            final_tokens.append(token)
                        else:
                            non_final_tokens.append(token)
                
                # Notify callback
                if self.on_tokens:
                    self.on_tokens(final_tokens, non_final_tokens)
                
                if res.get("finished"):
                    break
                    
        except ConnectionClosedOK:
            pass
        except Exception as e:
            if self.on_error and self._running.is_set():
                self.on_error(str(e))
    
    def start(self) -> bool:
        """Start transcription. Returns True if started successfully."""
        device_idx = self._find_microphone()
        
        if device_idx is None or self._audio is None:
            if self.on_error:
                self.on_error("No microphone found")
            return False
        
        # Open audio stream
        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=NUM_CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=device_idx,
            frames_per_buffer=CHUNK_SIZE
        )
        
        self._running.set()
        
        try:
            # Connect to WebSocket
            config = get_soniox_config(self.api_key, self.context)
            self._ws = connect(SONIOX_WEBSOCKET_URL)
            self._ws.send(json.dumps(config))
            
            if self.on_connected:
                self.on_connected()
            
            # Start microphone streaming thread
            self._mic_thread = threading.Thread(
                target=self._stream_microphone,
                daemon=True,
            )
            self._mic_thread.start()
            
            # Start receive thread
            self._recv_thread = threading.Thread(
                target=self._receive_messages,
                daemon=True,
            )
            self._recv_thread.start()
            
            return True
            
        except Exception as e:
            self.stop()
            if self.on_error:
                self.on_error(str(e))
            return False
    
    def stop(self) -> None:
        """Stop transcription and clean up resources."""
        self._running.clear()
        
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        
        if self._audio:
            try:
                self._audio.terminate()
            except Exception:
                pass
            self._audio = None
    
    def wait(self) -> None:
        """Wait for transcription to complete."""
        if self._recv_thread:
            self._recv_thread.join()

