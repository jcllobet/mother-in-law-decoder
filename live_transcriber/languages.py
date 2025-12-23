"""
Language configuration and utilities for all Soniox-supported languages.
"""

# All 60+ Soniox-supported languages with names and flag emojis
SONIOX_LANGUAGES = {
    "ar": {"name": "Arabic", "flag": "🇸🇦"},
    "eu": {"name": "Basque", "flag": "🪨"},
    "bs": {"name": "Bosnian", "flag": "🇧🇦"},
    "bg": {"name": "Bulgarian", "flag": "🇧🇬"},
    "ca": {"name": "Catalan", "flag": "🐈"},
    "zh": {"name": "Chinese", "flag": "🇨🇳"},
    "hr": {"name": "Croatian", "flag": "🇭🇷"},
    "cs": {"name": "Czech", "flag": "🇨🇿"},
    "da": {"name": "Danish", "flag": "🇩🇰"},
    "nl": {"name": "Dutch", "flag": "🇳🇱"},
    "en": {"name": "English", "flag": "🇺🇸"},
    "et": {"name": "Estonian", "flag": "🇪🇪"},
    "fi": {"name": "Finnish", "flag": "🇫🇮"},
    "fr": {"name": "French", "flag": "🇫🇷"},
    "de": {"name": "German", "flag": "🇩🇪"},
    "el": {"name": "Greek", "flag": "🇬🇷"},
    "he": {"name": "Hebrew", "flag": "🇮🇱"},
    "hi": {"name": "Hindi", "flag": "🇮🇳"},
    "hu": {"name": "Hungarian", "flag": "🇭🇺"},
    "id": {"name": "Indonesian", "flag": "🇮🇩"},
    "it": {"name": "Italian", "flag": "🇮🇹"},
    "ja": {"name": "Japanese", "flag": "🇯🇵"},
    "ko": {"name": "Korean", "flag": "🇰🇷"},
    "ms": {"name": "Malay", "flag": "🇲🇾"},
    "no": {"name": "Norwegian", "flag": "🇳🇴"},
    "fa": {"name": "Persian", "flag": "🇮🇷"},
    "pl": {"name": "Polish", "flag": "🇵🇱"},
    "pt": {"name": "Portuguese", "flag": "🇵🇹"},
    "ro": {"name": "Romanian", "flag": "🇷🇴"},
    "ru": {"name": "Russian", "flag": "🇷🇺"},
    "sr": {"name": "Serbian", "flag": "🇷🇸"},
    "sk": {"name": "Slovak", "flag": "🇸🇰"},
    "sl": {"name": "Slovenian", "flag": "🇸🇮"},
    "es": {"name": "Spanish", "flag": "🇪🇸"},
    "sv": {"name": "Swedish", "flag": "🇸🇪"},
    "tl": {"name": "Tagalog", "flag": "🇵🇭"},
    "th": {"name": "Thai", "flag": "🇹🇭"},
    "tr": {"name": "Turkish", "flag": "🇹🇷"},
    "uk": {"name": "Ukrainian", "flag": "🇺🇦"},
    "ur": {"name": "Urdu", "flag": "🇵🇰"},
    "vi": {"name": "Vietnamese", "flag": "🇻🇳"},
}


def get_language_name(code: str) -> str:
    """Get the display name for a language code."""
    lang = SONIOX_LANGUAGES.get(code)
    if lang:
        return lang["name"]
    return code.upper()


def get_language_flag(code: str) -> str:
    """Get the flag emoji for a language code."""
    lang = SONIOX_LANGUAGES.get(code)
    if lang:
        return lang["flag"]
    return "🌐"


def get_all_language_codes() -> list[str]:
    """Get all supported language codes."""
    return sorted(SONIOX_LANGUAGES.keys())


def search_languages(query: str) -> list[tuple[str, str]]:
    """
    Search languages by name or code.
    Returns list of (code, name) tuples sorted by relevance.
    """
    if not query:
        return [(code, lang["name"]) for code, lang in sorted(SONIOX_LANGUAGES.items())]

    query_lower = query.lower()
    results = []

    for code, lang in SONIOX_LANGUAGES.items():
        name = lang["name"]
        name_lower = name.lower()

        # Exact code match (highest priority)
        if code == query_lower:
            results.append((0, code, name))
        # Code starts with query
        elif code.startswith(query_lower):
            results.append((1, code, name))
        # Name starts with query
        elif name_lower.startswith(query_lower):
            results.append((2, code, name))
        # Name contains query
        elif query_lower in name_lower:
            results.append((3, code, name))

    # Sort by priority (lower number = higher priority), then alphabetically
    results.sort(key=lambda x: (x[0], x[2]))

    return [(code, name) for _, code, name in results]
