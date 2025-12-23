#!/usr/bin/env python3
"""
Live Translator
Real-time multilingual transcription and translation with interactive scroll mode.
"""

import argparse
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from live_transcriber import (
    Session,
    Transcriber,
    NegotiationUI,
    list_audio_devices,
)

# Default context for transcription
DEFAULT_CONTEXT = """This is a casual family conversation between people who speak different languages. The conversation may include family matters, daily life topics, stories, jokes, and personal anecdotes. Pay attention to conversational nuances, cultural references, and emotional tone."""


def main():
    parser = argparse.ArgumentParser(
        description="Live transcription and translation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Keyboard shortcuts:
  v - Enter scroll mode to view full transcript
  q - Save and quit

Scroll mode navigation:
  j/k or ↑↓ - Scroll up/down
  g/G - Jump to top/bottom
  q - Exit scroll mode
        """
    )
    parser.add_argument(
        "--session", "-s",
        type=str,
        default=None,
        help="Session name (all recordings will be grouped under this name)"
    )
    parser.add_argument(
        "--context", "-c",
        type=str,
        default=None,
        help="Context hint for better transcription accuracy"
    )
    parser.add_argument(
        "--device", "-d",
        type=int,
        default=None,
        help="Audio input device index (use --list-devices to see options)"
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio input devices and exit"
    )
    args = parser.parse_args()
    
    # List devices mode
    if args.list_devices:
        devices = list_audio_devices()
        print("Available audio input devices:")
        
        # Find which would be default (MacBook mic preferred)
        default_idx = None
        for idx, name in devices:
            if "macbook" in name.lower() and "microphone" in name.lower():
                default_idx = idx
                break
        
        for idx, name in devices:
            marker = " (default)" if idx == default_idx else ""
            print(f"  [{idx}] {name}{marker}")
        
        print("\nUse --device <index> to select a specific device.")
        sys.exit(0)
    
    # Require session name for normal operation
    if not args.session:
        parser.error("--session/-s is required")
    
    # Check for API keys
    soniox_key = os.environ.get("SONIOX_API_KEY")
    if not soniox_key:
        print("Error: Missing SONIOX_API_KEY. Set it in .env or environment.")
        sys.exit(1)
    
    # Type narrowing for linter
    assert soniox_key is not None

    # Set context
    context: str = args.context if args.context else DEFAULT_CONTEXT

    # Initialize base components
    base_dir = os.path.dirname(os.path.abspath(__file__))
    session = Session(args.session, base_dir)

    # Initialize transcriber and UI
    transcriber = Transcriber(
        api_key=soniox_key,
        session=session,
        context=context,
        device_index=args.device,
    )

    # Run full UI
    ui = NegotiationUI(
        session=session,
        transcriber=transcriber,
    )

    ui.run()


if __name__ == "__main__":
    main()
