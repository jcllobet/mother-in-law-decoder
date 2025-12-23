"""
Rich-based terminal UI for the negotiation assistant.
Terminal-native keyboard controls (only when terminal is focused).
"""

import sys
import select
import threading
import tty
import termios
from typing import Optional
from queue import Queue, Empty

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.live import Live

from .session import Session
from .transcription import Transcriber

# Display settings
LIVE_VIEW_LINES = 24
SCROLL_PAGE_SIZE = 20

# Christmas colors (matching language_selector.py)
CHRISTMAS_GREEN = "#165b33"
CHRISTMAS_GOLD = "#d4af37"
CHRISTMAS_RED = "#c41e3a"

# Language colors organized by linguistic family/region
# English is always white; similar languages share similar color tones
LANGUAGE_COLORS = {
    # === ENGLISH (always white) ===
    "en": "white",

    # === GERMANIC (cool blues/silver - winter/ice theme) ===
    "de": "#87ceeb",         # German - sky blue
    "nl": "#add8e6",         # Dutch - light blue
    "da": "#b0c4de",         # Danish - light steel blue
    "no": "#87cefa",         # Norwegian - light sky blue
    "sv": "#a0c4e8",         # Swedish - soft blue

    # === ROMANCE (warm golds/amber - warmth theme) ===
    "es": "#d4af37",         # Spanish - antique gold
    "fr": "#daa520",         # French - goldenrod
    "it": "#f0c05a",         # Italian - soft gold
    "pt": "#e6be5a",         # Portuguese - muted gold
    "ro": "#cda434",         # Romanian - darker gold
    "ca": "#d4a84b",         # Catalan - amber gold
    "gl": "#c9a227",         # Galician - old gold

    # === SLAVIC (purple/violet tones) ===
    "ru": "#dda0dd",         # Russian - plum
    "pl": "#d8bfd8",         # Polish - thistle
    "cs": "#e6a8d7",         # Czech - orchid pink
    "sk": "#dbb2d1",         # Slovak - light plum
    "uk": "#da70d6",         # Ukrainian - orchid
    "bg": "#d291bc",         # Bulgarian - pastel violet
    "sr": "#c9a0dc",         # Serbian - wisteria
    "hr": "#d7a9e3",         # Croatian - light orchid
    "bs": "#cba4d4",         # Bosnian - soft violet
    "sl": "#d3a4d9",         # Slovenian - lavender pink
    "mk": "#d8a1d4",         # Macedonian - mauve

    # === BALTIC & FINNO-UGRIC (teal/aqua - Baltic sea) ===
    "lt": "#40e0d0",         # Lithuanian - turquoise
    "lv": "#48d1cc",         # Latvian - medium turquoise
    "et": "#00ced1",         # Estonian - dark turquoise
    "fi": "#5f9ea0",         # Finnish - cadet blue
    "hu": "#20b2aa",         # Hungarian - light sea green

    # === GREEK & BASQUE (unique colors) ===
    "el": "#9acd32",         # Greek - yellow green (olive)
    "eu": "#cd853f",         # Basque - peru (unique)

    # === MIDDLE EASTERN & TURKIC (copper/bronze tones) ===
    "ar": "#cd7f32",         # Arabic - bronze
    "he": "#b87333",         # Hebrew - copper
    "fa": "#cc7722",         # Persian - ochre
    "tr": "#d2691e",         # Turkish - chocolate
    "ur": "#c2772e",         # Urdu - copper brown

    # === SOUTH ASIAN (coral/salmon - vibrant warm) ===
    "hi": "#ff7f50",         # Hindi - coral
    "gu": "#fa8072",         # Gujarati - salmon
    "mr": "#f08080",         # Marathi - light coral
    "pa": "#e9967a",         # Punjabi - dark salmon
    "ta": "#ffa07a",         # Tamil - light salmon
    "te": "#ff8c69",         # Telugu - salmon orange
    "ml": "#ff6f61",         # Malayalam - living coral

    # === EAST ASIAN (red tones - festive/lucky) ===
    "zh": "#c41e3a",         # Chinese - cardinal red
    "ja": "#dc143c",         # Japanese - crimson
    "ko": "#b22234",         # Korean - deep red

    # === SOUTHEAST ASIAN (green tones - tropical) ===
    "vi": "#90ee90",         # Vietnamese - light green
    "th": "#98fb98",         # Thai - pale green
    "id": "#8fbc8f",         # Indonesian - dark sea green
    "ms": "#66cdaa",         # Malay - medium aquamarine
    "tl": "#7cfc00",         # Tagalog - lawn green
}
DEFAULT_LANGUAGE_COLOR = "#d4af37"  # Gold fallback

# Speaker emoji + color pairs for differentiation (high contrast colors)
# Each speaker gets a unique emoji AND color for easy identification
SPEAKER_STYLES = [
    ("🎄", "#98fb98"),  # Christmas tree - pale green
    ("🎅", "#ff6b6b"),  # Santa - coral red
    ("✨", "#ffd700"),  # Star - gold
    ("🎁", "#ff69b4"),  # Gift box - hot pink
    ("🔔", "#ffb347"),  # Bell - pastel orange
    ("🕯️", "#dda0dd"),  # Candle - plum
    ("🧦", "#87ceeb"),  # Stocking - sky blue
    ("🍪", "#deb887"),  # Cookie - burlywood
    ("☃️", "#e0ffff"),  # Snowman - light cyan
    ("❄️", "#b0e0e6"),  # Snowflake - powder blue
    ("🦌", "#cd853f"),  # Reindeer - peru
    ("👵", "#f0e68c"),  # Grandma - khaki
    ("🎀", "#ffb6c1"),  # Ribbon - light pink
    ("🧣", "#20b2aa"),  # Scarf - light sea green
]

# Language flags are now handled by the languages module


class NegotiationUI:  # TODO: Rename to FamilyChatUI in future refactor
    """Rich-based terminal UI for family conversations with real-time keyboard controls."""
    
    def __init__(
        self,
        session: Session,
        transcriber: Transcriber,
    ):
        self.session = session
        self.transcriber = transcriber
        self.console = Console()
        
        self._running = threading.Event()
        self._non_final_tokens: list[dict] = []

        # Status
        self._status_message = ""
        self._error_message = ""
        
        # Scroll mode
        self._scroll_mode = False
        self._scroll_offset = 0
        self._scroll_lines: list[str] = []
        self._scroll_total_lines = 0
        
        # Keyboard (terminal-native, only captures when terminal focused)
        self._key_queue: Queue[str] = Queue()
        self._input_thread: Optional[threading.Thread] = None
        self._old_term_settings = None
    
    def _read_key(self) -> Optional[str]:
        """Read a single key from terminal (non-blocking)."""
        if select.select([sys.stdin], [], [], 0)[0]:
            ch = sys.stdin.read(1)
            if ch == '\x1b':  # Escape sequence
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    ch2 = sys.stdin.read(1)
                    if ch2 == '[':
                        if select.select([sys.stdin], [], [], 0.05)[0]:
                            ch3 = sys.stdin.read(1)
                            if ch3 == 'A':
                                return 'UP'
                            elif ch3 == 'B':
                                return 'DOWN'
                            elif ch3 == '5':
                                sys.stdin.read(1)  # consume ~
                                return 'PAGEUP'
                            elif ch3 == '6':
                                sys.stdin.read(1)  # consume ~
                                return 'PAGEDOWN'
                return 'ESC'
            return ch.lower()
        return None
    
    def _input_thread_func(self) -> None:
        """Background thread to read terminal input."""
        import time
        while self._running.is_set():
            try:
                key = self._read_key()
                if key:
                    self._key_queue.put(key)
                else:
                    time.sleep(0.05)  # Prevent busy-waiting
            except Exception:
                time.sleep(0.1)
    
    def _start_keyboard_listener(self) -> None:
        """Start terminal keyboard listener."""
        try:
            # Set terminal to raw mode (no echo, char-by-char input)
            self._old_term_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            
            self._input_thread = threading.Thread(target=self._input_thread_func, daemon=True)
            self._input_thread.start()
        except Exception:
            pass
    
    def _stop_keyboard_listener(self) -> None:
        """Restore terminal settings."""
        if self._old_term_settings:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_term_settings)
            except Exception:
                pass
    
    def _handle_key(self, key: str) -> None:
        """Handle a key press."""
        if self._scroll_mode:
            self._handle_scroll_key(key)
        else:
            self._handle_live_key(key)
    
    def _handle_live_key(self, key: str) -> None:
        """Handle key in live mode."""
        if key == 'v':
            self._enter_scroll_mode()
        elif key == 'q':
            self._running.clear()
    
    def _handle_scroll_key(self, key: str) -> None:
        """Handle key in scroll mode."""
        if key in ('q', 'ESC', 'v'):
            self._exit_scroll_mode()
        elif key in ('j', 'DOWN'):
            self._scroll_down()
        elif key in ('k', 'UP'):
            self._scroll_up()
        elif key in ('d', 'PAGEDOWN'):
            self._scroll_down(SCROLL_PAGE_SIZE - 2)
        elif key in ('u', 'PAGEUP'):
            self._scroll_up(SCROLL_PAGE_SIZE - 2)
        elif key == 'g':
            self._scroll_to_top()
        elif key == 'G':
            self._scroll_to_bottom()
    
    def _enter_scroll_mode(self) -> None:
        """Enter scroll mode."""
        if not self.session.final_tokens:
            self._error_message = "No transcript yet"
            return
        self._scroll_mode = True
        self._prepare_scroll_content()
        self._scroll_offset = max(0, self._scroll_total_lines - SCROLL_PAGE_SIZE)
    
    def _exit_scroll_mode(self) -> None:
        """Exit scroll mode."""
        self._scroll_mode = False
    
    def _prepare_scroll_content(self) -> None:
        """Prepare scroll content."""
        text = self._render_transcript_plain()
        self._scroll_lines = text.split("\n")
        self._scroll_total_lines = len(self._scroll_lines)
    
    def _scroll_up(self, n: int = 1) -> None:
        self._scroll_offset = max(0, self._scroll_offset - n)
    
    def _scroll_down(self, n: int = 1) -> None:
        max_off = max(0, self._scroll_total_lines - SCROLL_PAGE_SIZE)
        self._scroll_offset = min(max_off, self._scroll_offset + n)
    
    def _scroll_to_top(self) -> None:
        self._scroll_offset = 0
    
    def _scroll_to_bottom(self) -> None:
        self._scroll_offset = max(0, self._scroll_total_lines - SCROLL_PAGE_SIZE)
    
    def _on_tokens(self, final_tokens: list[dict], non_final_tokens: list[dict]) -> None:
        """Callback when tokens received."""
        self._non_final_tokens = non_final_tokens
    
    def _on_error(self, error: str) -> None:
        """Callback on error."""
        self._error_message = error
    
    def _on_connected(self) -> None:
        """Callback when connected."""
        self._status_message = "Listening..."
    
    def _render_transcript_plain(self) -> str:
        """Render transcript as plain text with parenthetical translations."""
        parts: list[str] = []
        current_speaker: Optional[int] = None

        # Buffers for accumulating original + translation pairs
        original_buffer = ""
        translation_buffer = ""

        for token in self.session.final_tokens:
            text = token.get("text", "")
            speaker = token.get("speaker")
            is_translation = token.get("translation_status") == "translation"
            source_lang = token.get("source_language")

            # Skip translations when source language equals target language
            if is_translation and source_lang == self.session.target_language:
                continue

            # Speaker changed - flush buffers, start new paragraph
            if speaker is not None and speaker != current_speaker:
                # Flush pending content
                if original_buffer:
                    parts.append(original_buffer)
                    if translation_buffer:
                        parts.append(f" ({translation_buffer.strip()})")
                original_buffer = ""
                translation_buffer = ""

                if current_speaker is not None:
                    parts.append("\n\n")
                current_speaker = speaker

                # Speaker header with emoji
                emoji, _ = self._get_speaker_style(speaker)
                profile = self.session.get_speaker_profile(speaker)
                parts.append(f"{emoji} {profile.get_label()}: ")
                text = text.lstrip()

            # Accumulate text
            if is_translation:
                translation_buffer += text
            else:
                # If we have pending translation, flush first
                if translation_buffer:
                    parts.append(original_buffer)
                    parts.append(f" ({translation_buffer.strip()})")
                    original_buffer = ""
                    translation_buffer = ""
                original_buffer += text

        # Final flush
        if original_buffer:
            parts.append(original_buffer)
            if translation_buffer:
                parts.append(f" ({translation_buffer.strip()})")

        return "".join(parts)
    
    def _get_speaker_style(self, speaker_id: int | str) -> tuple[str, str]:
        """Get a unique emoji + color pair for a speaker."""
        sid = int(speaker_id) if isinstance(speaker_id, str) else speaker_id
        return SPEAKER_STYLES[sid % len(SPEAKER_STYLES)]

    def _get_language_color(self, language: str) -> str:
        """Get color for a language (English = white, regional families share tones)."""
        return LANGUAGE_COLORS.get(language, DEFAULT_LANGUAGE_COLOR)

    def _get_language_flag(self, language: str) -> str:
        """Get flag emoji for a language."""
        from .languages import get_language_flag
        return get_language_flag(language)

    def _flush_buffers(
        self,
        text: Text,
        original: str,
        translation: str,
        lang: str,
        is_final: bool = True
    ) -> None:
        """Flush accumulated original + translation to text with parenthetical format."""
        if not original and not translation:
            return

        lang_color = self._get_language_color(lang) if lang else DEFAULT_LANGUAGE_COLOR

        # Apply styling based on finality
        if is_final:
            if original:
                text.append(original, style=lang_color)
            if translation:
                text.append(" (", style="dim")
                text.append(translation.strip(), style="white")
                text.append(")", style="dim")
        else:
            # Non-final (in-progress) text is dim and italic
            if original:
                text.append(original, style=f"dim italic {lang_color}")
            if translation:
                text.append(" (", style="dim")
                text.append(translation.strip(), style="dim italic white")
                text.append(")", style="dim")

    def _render_transcript(self) -> Text:
        """Render transcript with inline parenthetical translations and language colors."""
        text = Text()
        current_speaker: Optional[int | str] = None

        # Buffers for accumulating original + translation pairs
        original_buffer = ""
        translation_buffer = ""
        current_lang: Optional[str] = None
        buffer_is_final = True

        all_tokens = self.session.final_tokens + self._non_final_tokens

        for token in all_tokens:
            token_text = token.get("text", "")
            speaker = token.get("speaker")
            language = token.get("language")
            is_translation = token.get("translation_status") == "translation"
            is_final = token.get("is_final", True)
            source_lang = token.get("source_language")

            # Skip translations when source language equals target language
            if is_translation and source_lang == self.session.target_language:
                continue

            # Speaker changed - flush buffers, start new paragraph
            if speaker is not None and speaker != current_speaker:
                # Flush any pending content
                self._flush_buffers(text, original_buffer, translation_buffer, current_lang, buffer_is_final)
                original_buffer = ""
                translation_buffer = ""
                buffer_is_final = True

                if current_speaker is not None:
                    text.append("\n\n")
                current_speaker = speaker

                # Speaker header with emoji and unique color
                emoji, speaker_color = self._get_speaker_style(speaker)
                profile = self.session.get_speaker_profile(speaker)
                label = profile.get_label()
                text.append(f"{emoji} {label}: ", style=f"bold {speaker_color}")
                current_lang = language
                token_text = token_text.lstrip()

            # Track if buffer contains non-final content
            if not is_final:
                buffer_is_final = False

            # Accumulate text
            if is_translation:
                translation_buffer += token_text
            else:
                # If we have pending translation, flush first (phrase complete)
                if translation_buffer:
                    self._flush_buffers(text, original_buffer, translation_buffer, current_lang, buffer_is_final)
                    original_buffer = ""
                    translation_buffer = ""
                    buffer_is_final = is_final
                original_buffer += token_text
                current_lang = language

        # Final flush
        self._flush_buffers(text, original_buffer, translation_buffer, current_lang, buffer_is_final)
        return text
    
    def _render_live_transcript(self) -> Text:
        """Render last N lines of transcript."""
        full = self._render_transcript()
        if not full:
            return Text("Waiting for speech...", style="dim italic")

        lines = str(full).split("\n")
        if len(lines) <= LIVE_VIEW_LINES:
            return full

        visible = lines[-LIVE_VIEW_LINES:]
        result = Text()
        result.append(f"↑ {len(lines) - LIVE_VIEW_LINES} more (v=scroll) ", style=f"dim {CHRISTMAS_GREEN}")
        result.append("\n".join(visible))
        return result
    
    def _render_status_bar(self) -> Text:
        """Render status bar with Christmas theme."""
        text = Text()

        if self._scroll_mode:
            text.append(" SCROLL ", style=f"black on {CHRISTMAS_RED}")
            start = self._scroll_offset + 1
            end = min(self._scroll_offset + SCROLL_PAGE_SIZE, self._scroll_total_lines)
            text.append(f" {start}-{end}/{self._scroll_total_lines}", style=CHRISTMAS_RED)
        else:
            text.append(" LIVE ", style=f"black on {CHRISTMAS_GREEN}")

        text.append(f" │ {self.session.name}", style="bold")
        text.append(f" │ {len(self.session.final_tokens)} tokens", style="dim")

        # Show language configuration
        source_langs = ",".join(self.session.source_languages)
        text.append(f" │ Langs: {source_langs} → {self.session.target_language}", style="dim")

        if self._error_message:
            text.append(f" │ {self._error_message}", style=CHRISTMAS_RED)
            self._error_message = ""
        elif self._status_message:
            text.append(f" │ {self._status_message}", style="dim")

        return text
    
    def _render_hotkey_bar(self) -> Text:
        """Render hotkey hints with Christmas theme."""
        text = Text()
        if self._scroll_mode:
            for k, d in [("j↓k↑", "scroll"), ("du", "page"), ("gG", "ends"), ("q", "exit")]:
                text.append(f" {k}", style=CHRISTMAS_GOLD)
                text.append(f"={d}", style="dim")
        else:
            for k, d in [("v", "scroll"), ("q", "quit")]:
                text.append(f" {k}", style=CHRISTMAS_GOLD)
                text.append(f"={d}", style="dim")
        return text
    
    def _build_scroll_display(self) -> Group:
        """Build scroll display with Christmas theme."""
        header = Text("🎙 SCROLL MODE ", style=f"bold {CHRISTMAS_RED}")
        header.append("(j/k=scroll, q=exit)", style="dim")

        visible = self._scroll_lines[self._scroll_offset:self._scroll_offset + SCROLL_PAGE_SIZE]
        content = "\n".join(visible) if visible else "No content"

        return Group(
            Panel(header, style=CHRISTMAS_RED),
            Panel(Text(content), border_style=CHRISTMAS_RED),
            self._render_status_bar(),
            self._render_hotkey_bar(),
        )
    
    def _build_display(self) -> Group:
        """Build main display with Christmas theme."""
        if self._scroll_mode:
            return self._build_scroll_display()

        parts = []

        # Header
        header = Text("🎄 Live Translator", style=f"bold {CHRISTMAS_GREEN}")
        parts.append(Panel(header, style=CHRISTMAS_GREEN))

        # Main transcript panel
        parts.append(Panel(
            self._render_live_transcript(),
            title=f"[bold {CHRISTMAS_GREEN}]Live Transcript[/]",
            border_style=CHRISTMAS_GREEN,
        ))

        # Status and hotkeys
        parts.append(self._render_status_bar())
        parts.append(self._render_hotkey_bar())

        return Group(*parts)
    
    def run(self) -> None:
        """Run the UI."""
        self._running.set()
        
        # Setup callbacks
        self.transcriber.on_tokens = self._on_tokens
        self.transcriber.on_error = self._on_error
        self.transcriber.on_connected = self._on_connected
        
        # Initial display
        self.console.clear()
        self.console.print(f"[bold {CHRISTMAS_GREEN}]🎄 Live Translator[/]")

        if self.session.was_resumed:
            info = self.session.get_resume_info()
            if info:
                self.console.print(f"[{CHRISTMAS_GOLD}]🎁 Resuming ({info['token_count']} tokens)[/]")

        self.console.print("[dim]Connecting...[/]")
        if not self.transcriber.start():
            self.console.print(f"[{CHRISTMAS_RED}]Failed to start[/]")
            return

        self.console.print(f"[{CHRISTMAS_GREEN}]✓[/] {self.transcriber.device_name}")
        self.console.print(f"[dim]Keys: [{CHRISTMAS_GOLD}]v[/]=scroll [{CHRISTMAS_GOLD}]q[/]=quit[/]")
        self.console.print()
        
        self._start_keyboard_listener()
        
        try:
            import time
            with Live(self._build_display(), console=self.console, refresh_per_second=4, vertical_overflow="crop") as live:
                while self._running.is_set() and self.transcriber.is_running:
                    # Process keypresses
                    try:
                        while True:
                            key = self._key_queue.get_nowait()
                            self._handle_key(key)
                    except Empty:
                        pass
                    
                    # Update scroll content
                    if self._scroll_mode:
                        self._prepare_scroll_content()
                    
                    live.update(self._build_display())
                    time.sleep(0.1)  # Control update rate
                    
        except KeyboardInterrupt:
            pass
        finally:
            self._stop_keyboard_listener()
            self._running.clear()
            self.transcriber.stop()
            
            self.console.print()
            if self.session.final_tokens:
                self.console.print(f"[{CHRISTMAS_GOLD}]Saving...[/]")
                path = self.session.save_segment()
                self.console.print(f"[{CHRISTMAS_GREEN}]✓[/] {path}")
