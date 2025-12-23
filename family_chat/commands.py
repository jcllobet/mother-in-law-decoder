"""
Command parser and handler for the live translator.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, Any


class CommandType(Enum):
    """Types of commands available."""
    BACKGROUND = "background"
    FOREGROUND = "foreground"
    SCROLL = "scroll"
    SAVE = "save"
    QUIT = "quit"
    UNKNOWN = "unknown"


@dataclass
class Command:
    """Parsed command with type and arguments."""
    type: CommandType
    args: str = ""
    raw: str = ""


class CommandHandler:
    """Parse and dispatch commands."""
    
    # Command aliases
    ALIASES = {
        "/b": CommandType.BACKGROUND,
        "/bg": CommandType.BACKGROUND,
        "/fg": CommandType.FOREGROUND,
        "/foreground": CommandType.FOREGROUND,
        "/v": CommandType.SCROLL,
        "/view": CommandType.SCROLL,
        "/scroll": CommandType.SCROLL,
        "/save": CommandType.SAVE,
        "/q": CommandType.QUIT,
        "/quit": CommandType.QUIT,
    }
    
    def __init__(self):
        self._handlers: dict[CommandType, Callable[[Command], Any]] = {}
    
    def register(self, cmd_type: CommandType, handler: Callable[[Command], Any]) -> None:
        """Register a handler for a command type."""
        self._handlers[cmd_type] = handler
    
    def parse(self, input_str: str) -> Optional[Command]:
        """Parse input string into a command. Returns None if not a command."""
        input_str = input_str.strip()
        
        if not input_str.startswith("/"):
            return None
        
        parts = input_str.split(maxsplit=1)
        cmd_str = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        cmd_type = self.ALIASES.get(cmd_str, CommandType.UNKNOWN)
        
        return Command(type=cmd_type, args=args, raw=input_str)
    
    def execute(self, cmd: Command) -> Any:
        """Execute a command. Returns the handler's result."""
        handler = self._handlers.get(cmd.type)
        if handler:
            return handler(cmd)
        return None
    
    def handle_input(self, input_str: str) -> tuple[bool, Any]:
        """
        Handle user input. Returns (was_command, result).
        If not a command, returns (False, None).
        """
        cmd = self.parse(input_str)
        if cmd is None:
            return (False, None)
        
        result = self.execute(cmd)
        return (True, result)

