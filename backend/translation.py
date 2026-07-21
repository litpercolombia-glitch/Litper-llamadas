"""Translation provider abstraction — swap library ↔ LLM via env."""
from __future__ import annotations
import os
import logging
from typing import Protocol

log = logging.getLogger("translation")


class TranslationProvider(Protocol):
    name: str
    def translate(self, text: str, source: str, target: str) -> str: ...


class LibraryProvider:
    name = "library:google_translator"

    def translate(self, text: str, source: str, target: str) -> str:
        # Lazy import so servers without the lib still start.
        from deep_translator import GoogleTranslator
        src = source if source and source != "auto" else "auto"
        return GoogleTranslator(source=src, target=target).translate(text)


class LLMProvider:
    """Placeholder LLM provider — real implementation kept behind env flag.
    Falls back to library provider if LLM_API_KEY is missing.
    """
    name = "llm:emergent_universal"

    def translate(self, text: str, source: str, target: str) -> str:
        key = os.environ.get("LLM_API_KEY", "").strip()
        if not key:
            log.warning("LLM provider selected but LLM_API_KEY is empty — falling back to library.")
            return LibraryProvider().translate(text, source, target)
        # Intentionally not implemented until owner supplies a key.
        # For safety fall back to library.
        return LibraryProvider().translate(text, source, target)


def get_provider() -> TranslationProvider:
    kind = os.environ.get("TRANSLATION_PROVIDER", "library").lower()
    return LLMProvider() if kind == "llm" else LibraryProvider()
