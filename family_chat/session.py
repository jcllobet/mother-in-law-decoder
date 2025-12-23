"""
Session management and speaker profiling for transcription sessions.
"""

import json
import os
import wave
import subprocess
from datetime import datetime
from typing import Optional
from collections import defaultdict

# Audio settings (shared with transcription module)
SAMPLE_RATE = 16000
NUM_CHANNELS = 1

# Language confidence threshold
LANGUAGE_CONFIDENCE_THRESHOLD = 0.5
# Samples needed before labeling speaker type
MIN_SAMPLES_FOR_LABELING = 10


class SpeakerProfile:
    """Track language usage for a speaker."""
    
    def __init__(self, speaker_id: int):
        self.speaker_id = speaker_id
        self.language_counts: dict[str, int] = defaultdict(int)
        self.last_language: Optional[str] = None
        self.total_samples = 0
    
    def add_sample(self, language: str) -> None:
        """Record a language sample for this speaker."""
        self.language_counts[language] += 1
        self.last_language = language
        self.total_samples += 1
    
    def get_dominant_language(self) -> Optional[str]:
        """Get the most used language, or None if no samples."""
        if not self.language_counts:
            return None
        return max(self.language_counts, key=self.language_counts.get)
    
    def get_speaker_type(self) -> Optional[str]:
        """Classify speaker after enough samples."""
        if self.total_samples < MIN_SAMPLES_FOR_LABELING:
            return None

        # TODO: Language generalization - Currently assumes English/Chinese binary.
        # This hardcoded en/zh logic should be generalized to support any language pair
        # detected in the conversation (e.g., Bulgarian/English, Spanish/English, etc.).
        en_count = self.language_counts.get("en", 0)
        zh_count = self.language_counts.get("zh", 0)
        total = en_count + zh_count

        if total == 0:
            return None

        en_ratio = en_count / total
        zh_ratio = zh_count / total

        # More than 80% one language = monolingual
        if en_ratio >= 0.8:
            return "English"
        elif zh_ratio >= 0.8:
            return "Chinese"
        else:
            return "Bilingual"
    
    def get_label(self) -> str:
        """Get display label for speaker."""
        speaker_type = self.get_speaker_type()
        if speaker_type:
            return f"{speaker_type} Speaker {self.speaker_id}"
        return f"Speaker {self.speaker_id}"
    
    # TODO: Language generalization - Replace with is_source_language_speaker().
    # This method name and logic are hardcoded to Chinese. Should be generalized
    # to detect if speaker uses the "source" language (non-English language being translated).
    def is_chinese_speaker(self) -> bool:
        """Check if speaker primarily uses Chinese."""
        speaker_type = self.get_speaker_type()
        return speaker_type in ("Chinese", "Bilingual")
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "language_counts": dict(self.language_counts),
            "last_language": self.last_language,
            "total_samples": self.total_samples,
        }
    
    @classmethod
    def from_dict(cls, speaker_id: int, data: dict) -> "SpeakerProfile":
        """Deserialize from dictionary."""
        profile = cls(speaker_id)
        profile.language_counts = defaultdict(int, data.get("language_counts", {}))
        profile.last_language = data.get("last_language")
        profile.total_samples = data.get("total_samples", 0)
        return profile


class Session:
    """Manage a transcription session with state persistence."""
    
    def __init__(self, name: str, base_dir: str):
        self.name = name
        self.base_dir = base_dir
        self.session_dir = os.path.join(base_dir, "live-conversations", name)
        self.state_file = os.path.join(self.session_dir, "session_state.json")
        self.speaker_profiles: dict[int, SpeakerProfile] = {}
        self.final_tokens: list[dict] = []
        self.segment_count = 0
        self.audio_frames: list[bytes] = []
        self._resumed = False
        
        # Create session directory
        os.makedirs(self.session_dir, exist_ok=True)
        
        # Load existing state if resuming
        self._load_state()
    
    @property
    def was_resumed(self) -> bool:
        """Check if session was resumed from existing state."""
        return self._resumed
    
    def _load_state(self) -> None:
        """Load session state if it exists."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                
                self.segment_count = state.get("segment_count", 0)
                self.final_tokens = state.get("tokens", [])
                
                # Restore speaker profiles
                for sid, profile_data in state.get("speaker_profiles", {}).items():
                    self.speaker_profiles[int(sid)] = SpeakerProfile.from_dict(
                        int(sid), profile_data
                    )
                
                self._resumed = True
            except Exception:
                pass  # Start fresh if state is corrupted
    
    def get_resume_info(self) -> Optional[dict]:
        """Get information about resumed session."""
        if not self._resumed:
            return None
        return {
            "segment_count": self.segment_count,
            "token_count": len(self.final_tokens),
            "speaker_count": len(self.speaker_profiles),
        }
    
    def save_state(self) -> None:
        """Save current session state."""
        state = {
            "name": self.name,
            "updated": datetime.now().isoformat(),
            "segment_count": self.segment_count,
            "tokens": self.final_tokens,
            "speaker_profiles": {
                sid: profile.to_dict()
                for sid, profile in self.speaker_profiles.items()
            }
        }
        
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def get_speaker_profile(self, speaker_id: int) -> SpeakerProfile:
        """Get or create speaker profile."""
        if speaker_id not in self.speaker_profiles:
            self.speaker_profiles[speaker_id] = SpeakerProfile(speaker_id)
        return self.speaker_profiles[speaker_id]
    
    def add_audio_frame(self, frame: bytes) -> None:
        """Add audio frame to buffer."""
        self.audio_frames.append(frame)
    
    def add_token(self, token: dict) -> None:
        """Add a finalized token to the session."""
        self.final_tokens.append(token)
    
    # TODO: Language generalization - Replace with get_source_language_tokens().
    # Hardcoded to filter for Chinese ("zh"). Should be generalized to filter
    # for any non-English source language detected in the conversation.
    def get_chinese_tokens(self) -> list[dict]:
        """Get all tokens from Chinese speakers or in Chinese language."""
        chinese_tokens = []
        for token in self.final_tokens:
            language = token.get("language")
            if language == "zh":
                chinese_tokens.append(token)
        return chinese_tokens
    
    def get_tokens_by_speaker(self, speaker_id: int) -> list[dict]:
        """Get all tokens from a specific speaker."""
        return [t for t in self.final_tokens if t.get("speaker") == speaker_id]
    
    def save_segment(self) -> str:
        """Save current segment (transcript + audio)."""
        self.segment_count += 1
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = f"segment_{self.segment_count:03d}_{timestamp}"
        
        # Save transcript JSON
        json_path = os.path.join(self.session_dir, f"{base_name}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "session": self.name,
                "segment": self.segment_count,
                "saved": datetime.now().isoformat(),
                "tokens": self.final_tokens,
                "speaker_profiles": {
                    sid: {
                        "type": profile.get_speaker_type(),
                        "label": profile.get_label(),
                        "language_counts": dict(profile.language_counts),
                    }
                    for sid, profile in self.speaker_profiles.items()
                }
            }, f, ensure_ascii=False, indent=2)
        
        # Save transcript TXT
        txt_path = os.path.join(self.session_dir, f"{base_name}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(self.render_plain_text())
        
        # Save audio
        audio_path = None
        if self.audio_frames:
            audio_path = self._save_audio(base_name)
        
        # Save session state
        self.save_state()
        
        return json_path
    
    def _save_audio(self, base_name: str) -> str:
        """Save audio frames to WAV, then convert to MP3 if possible."""
        wav_path = os.path.join(self.session_dir, f"{base_name}.wav")
        mp3_path = os.path.join(self.session_dir, f"{base_name}.mp3")
        
        # Save WAV
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(NUM_CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(self.audio_frames))
        
        # Try to convert to MP3 using ffmpeg
        try:
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-qscale:a", "2", mp3_path],
                capture_output=True,
                timeout=60
            )
            if result.returncode == 0:
                os.remove(wav_path)  # Remove WAV if MP3 succeeded
                return mp3_path
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # ffmpeg not available or timed out
        
        return wav_path
    
    def render_plain_text(self) -> str:
        """Render tokens as plain text."""
        text_parts: list[str] = []
        current_speaker: Optional[int] = None
        current_language: Optional[str] = None
        current_is_translation: bool = False
        
        for token in self.final_tokens:
            text = token.get("text", "")
            speaker = token.get("speaker")
            language = token.get("language")
            is_translation = token.get("translation_status") == "translation"
            
            # Skip translations of English (we only want Chinese translations)
            source_lang = token.get("source_language")
            if is_translation and source_lang == "en":
                continue
            
            if speaker is not None and speaker != current_speaker:
                if current_speaker is not None:
                    text_parts.append("\n\n")
                current_speaker = speaker
                current_language = None
                current_is_translation = False
                profile = self.get_speaker_profile(speaker)
                text_parts.append(f"{profile.get_label()}:")
            
            # Language or translation status changed
            lang_changed = language is not None and language != current_language
            translation_changed = is_translation != current_is_translation
            
            if lang_changed or translation_changed:
                current_language = language
                current_is_translation = is_translation
                
                if is_translation:
                    text_parts.append(f"\n  ↳ [{language}] ")
                else:
                    text_parts.append(f"\n[{language}] ")
                text = text.lstrip()
            
            text_parts.append(text)
        
        return "".join(text_parts).strip()


def resolve_language(token: dict, session: Session) -> str:
    """
    Resolve the language for a token, using speaker history if confidence is low.
    Also tracks the language sample for the speaker.
    """
    speaker = token.get("speaker")
    language: Optional[str] = token.get("language")
    confidence: float = token.get("language_confidence", 1.0)
    
    if speaker is None:
        return language if language is not None else "en"
    
    profile = session.get_speaker_profile(speaker)
    last_lang = profile.last_language
    
    # If confidence is below threshold, use last known language
    if confidence < LANGUAGE_CONFIDENCE_THRESHOLD and last_lang is not None:
        return last_lang
    
    # Record this language sample
    if language is not None:
        profile.add_sample(language)
        return language
    
    if last_lang is not None:
        return last_lang
    return "en"

