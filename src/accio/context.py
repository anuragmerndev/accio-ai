"""Frontmost-app detection: re-export the platform backend.

See accio.platform.darwin.context / accio.platform.windows.context for the
concrete implementation selected at import time.
"""

from accio.platform import context

frontmost_app_name = context.frontmost_app_name
tone_for_app = context.tone_for_app

# Exposed so tests and inspection tools can introspect the per-platform map
APP_TONES = context.APP_TONES

__all__ = ["frontmost_app_name", "tone_for_app", "APP_TONES"]
