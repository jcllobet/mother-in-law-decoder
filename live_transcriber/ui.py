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

# Speaker colors (cycle through for different speakers)
SPEAKER_COLORS = [
    "bright_green",
    "bright_cyan",
    "bright_magenta", 
    "bright_yellow",
    "bright_blue",
    "bright_red",
    "green",
    "cyan",
]

# Language flags
# TODO: Language generalization - Add more language flags.
# Currently only supports 4 languages. Expand to cover all Soniox-supported languages
# including Bulgarian (🇧🇬), Russian (🇷🇺), Spanish (🇪🇸), French (🇫🇷), etc.
LANGUAGE_FLAGS = {
    "en": "🇺🇸",
    "zh": "🇨🇳",
    "he": "🇮🇱",
    "ca": "🇪🇸",  # Catalan - using Spain flag
}


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
        """Render transcript as plain text."""
        parts: list[str] = []
        current_speaker: Optional[int] = None
        current_language: Optional[str] = None
        current_is_translation: bool = False
        
        for token in self.session.final_tokens:
            text = token.get("text", "")
            speaker = token.get("speaker")
            language = token.get("language")
            is_translation = token.get("translation_status") == "translation"
            source_lang = token.get("source_language")
            
            if is_translation and source_lang == "en":
                continue
            
            if speaker is not None and speaker != current_speaker:
                if current_speaker is not None:
                    parts.append("\n\n")
                current_speaker = speaker
                current_language = None
                current_is_translation = False
                profile = self.session.get_speaker_profile(speaker)
                parts.append(f"{profile.get_label()}:")
            
            lang_changed = language is not None and language != current_language
            translation_changed = is_translation != current_is_translation
            
            if lang_changed or translation_changed:
                current_language = language
                current_is_translation = is_translation
                if is_translation:
                    parts.append(f"\n  ↳ [{language}] ")
                else:
                    parts.append(f"\n[{language}] ")
                text = text.lstrip()
            
            parts.append(text)
        
        return "".join(parts)
    
    def _get_speaker_color(self, speaker_id: int | str) -> str:
        """Get a unique color for a speaker."""
        sid = int(speaker_id) if isinstance(speaker_id, str) else speaker_id
        return SPEAKER_COLORS[sid % len(SPEAKER_COLORS)]
    
    def _get_language_flag(self, language: str) -> str:
        """Get flag emoji for a language."""
        return LANGUAGE_FLAGS.get(language, "🌐")
    
    def _render_transcript(self) -> Text:
        """Render transcript as Rich Text - flowing paragraphs."""
        text = Text()
        current_speaker: Optional[int | str] = None
        current_is_translation: bool = False
        current_speaker_color: str = "white"
        
        all_tokens = self.session.final_tokens + self._non_final_tokens
        
        for token in all_tokens:
            token_text = token.get("text", "")
            speaker = token.get("speaker")
            language = token.get("language")
            is_translation = token.get("translation_status") == "translation"
            is_final = token.get("is_final", True)
            source_lang = token.get("source_language")
            
            if is_translation and source_lang == "en":
                continue
            
            # Speaker changed - new paragraph
            if speaker is not None and speaker != current_speaker:
                if current_speaker is not None:
                    text.append("\n\n")
                current_speaker = speaker
                current_is_translation = False
                profile = self.session.get_speaker_profile(speaker)
                
                # Use unique color per speaker
                current_speaker_color = self._get_speaker_color(speaker)
                flag = self._get_language_flag(language) if language else ""
                text.append(f"{profile.get_label()}: {flag} ", style=f"bold {current_speaker_color}")
                token_text = token_text.lstrip()
            
            # Translation line - indent on new line
            if is_translation and not current_is_translation:
                current_is_translation = True
                flag = self._get_language_flag(language) if language else ""
                text.append(f"\n  ↳ {flag} ", style=f"dim {current_speaker_color}")
                token_text = token_text.lstrip()
            elif not is_translation and current_is_translation:
                # Switching back from translation to original
                current_is_translation = False
                flag = self._get_language_flag(language) if language else ""
                text.append(f"\n{flag} ", style=current_speaker_color)
                token_text = token_text.lstrip()
            
            # Color text based on speaker, with variations for state
            if not is_final:
                text.append(token_text, style=f"dim italic {current_speaker_color}")
            elif is_translation:
                text.append(token_text, style=f"italic {current_speaker_color}")
            else:
                text.append(token_text, style=current_speaker_color)
        
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
        result.append(f"↑ {len(lines) - LIVE_VIEW_LINES} more (v=scroll) ", style="dim magenta")
        result.append("\n".join(visible))
        return result
    
    def _render_status_bar(self) -> Text:
        """Render status bar."""
        text = Text()
        
        if self._scroll_mode:
            text.append(" SCROLL ", style="black on magenta")
            start = self._scroll_offset + 1
            end = min(self._scroll_offset + SCROLL_PAGE_SIZE, self._scroll_total_lines)
            text.append(f" {start}-{end}/{self._scroll_total_lines}", style="magenta")
        else:
            text.append(" LIVE ", style="black on green")
        
        text.append(f" │ {self.session.name}", style="bold")
        text.append(f" │ {len(self.session.final_tokens)} tokens", style="dim")
        
        if self._error_message:
            text.append(f" │ {self._error_message}", style="red")
            self._error_message = ""
        elif self._status_message:
            text.append(f" │ {self._status_message}", style="dim")
        
        return text
    
    def _render_hotkey_bar(self) -> Text:
        """Render hotkey hints."""
        text = Text()
        if self._scroll_mode:
            for k, d in [("j↓k↑", "scroll"), ("du", "page"), ("gG", "ends"), ("q", "exit")]:
                text.append(f" {k}", style="cyan")
                text.append(f"={d}", style="dim")
        else:
            for k, d in [("v", "scroll"), ("q", "quit")]:
                text.append(f" {k}", style="cyan")
                text.append(f"={d}", style="dim")
        return text
    
    def _build_scroll_display(self) -> Group:
        """Build scroll display."""
        header = Text("🎙 SCROLL MODE ", style="bold magenta")
        header.append("(j/k=scroll, q=exit)", style="dim")
        
        visible = self._scroll_lines[self._scroll_offset:self._scroll_offset + SCROLL_PAGE_SIZE]
        content = "\n".join(visible) if visible else "No content"
        
        return Group(
            Panel(header, style="magenta"),
            Panel(Text(content), border_style="magenta"),
            self._render_status_bar(),
            self._render_hotkey_bar(),
        )
    
    def _build_display(self) -> Group:
        """Build main display."""
        if self._scroll_mode:
            return self._build_scroll_display()
        
        parts = []

        # Header
        header = Text("🎙 Live Translator", style="bold")
        parts.append(Panel(header, style="blue"))

        # Main transcript panel
        parts.append(Panel(
            self._render_live_transcript(),
            title="[bold]Live Transcript[/]",
            border_style="blue",
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
        self.console.print("[bold blue]🎙 Live Translator[/]")

        if self.session.was_resumed:
            info = self.session.get_resume_info()
            if info:
                self.console.print(f"[yellow]📂 Resuming ({info['token_count']} tokens)[/]")

        self.console.print("[dim]Connecting...[/]")
        if not self.transcriber.start():
            self.console.print("[red]Failed to start[/]")
            return

        self.console.print(f"[green]✓[/] {self.transcriber.device_name}")
        self.console.print("[dim]Keys: v=scroll q=quit[/]")
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
                self.console.print("[yellow]Saving...[/]")
                path = self.session.save_segment()
                self.console.print(f"[green]✓[/] {path}")
