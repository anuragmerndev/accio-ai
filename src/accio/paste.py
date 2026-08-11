"""Text insertion: re-export the platform backend.

The actual implementation lives in accio.platform.darwin.paste (macOS) or
accio.platform.windows.paste (Windows). This shim keeps callers doing
`from accio.paste import paste_text` portable.
"""

from accio.platform import paste

paste_text = paste.paste_text
copy_only = paste.copy_only

__all__ = ["paste_text", "copy_only"]
