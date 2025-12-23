"""
Family Conversation Decoder - Live transcription and translation.

Modes:
  - Full: NegotiationUI with interactive scroll mode
  - Minimal: run_simple_transcription for clean demos
"""

from .session import Session, SpeakerProfile
from .transcription import Transcriber, SAMPLE_RATE, NUM_CHANNELS, CHUNK_SIZE, SUPPORTED_LANGUAGES, list_audio_devices
from .ui import NegotiationUI
from .commands import CommandHandler
from .simple_ui import run_simple_transcription

__all__ = [
    "Session",
    "SpeakerProfile",
    "Transcriber",
    "NegotiationUI",
    "CommandHandler",
    "run_simple_transcription",
    "list_audio_devices",
    "SUPPORTED_LANGUAGES",
    "SAMPLE_RATE",
    "NUM_CHANNELS",
    "CHUNK_SIZE",
]

