# Wisper — Local, Private Wispr Flow Clone (Design)

Date: 2026-07-02
Status: Approved for implementation (autonomous /goal session; decisions flagged to user)

## Goal

A macOS menu-bar dictation app that replicates Wispr Flow's core loop — hold a key,
speak, release, get cleaned-up text pasted into whatever app has focus — with **zero
network calls**. All models run locally on Apple Silicon (M4, 16 GB).

## Background (from architecture research)

Wispr Flow itself is 100% cloud: on-device capture → Baseten GPU ASR (<200 ms) →
fine-tuned Llama cleanup (<200 ms) → clipboard-paste insertion, <700 ms p99
end-to-end. Key reproducible design choices:

- **Batch-per-utterance, not streaming** — waiting for the full utterance is what
  lets the LLM rewrite (filler removal, self-corrections, tone) instead of
  transcribing verbatim.
- **Insertion is clipboard simulation** — save pasteboard, set text, synthesize
  Cmd+V via CGEvent (Accessibility permission), restore pasteboard.
- **Context = frontmost app name** (tone) + text around cursor (continuation).

Proven local stacks (VoiceInk, Handy, Superwhisper): whisper.cpp / WhisperKit /
Parakeet for ASR + small local LLM for polish.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Platform | macOS only | User's machine; CGEvent/NSPasteboard are macOS APIs |
| Language | Python 3.12 (uv-managed) | Fastest to working pipeline; user (JS/MERN background) can read/modify; MLX bindings mature |
| ASR | `parakeet-mlx` (Parakeet TDT 0.6B); `mlx-whisper` fallback | Parakeet ~10x faster than Whisper on short utterances on Apple Silicon; both fully local |
| Polish | Two-tier: rule-based always; optional local LLM via `mlx-lm` (small 4-bit instruct model, Qwen class) | Rules give instant filler/dictionary handling with zero model cost; LLM adds tone + self-correction rewrites; graceful degrade if model missing |
| Hotkey | Hold **Right Option** (push-to-talk), configurable | Fn/Globe key is not reliably capturable outside Apple private APIs; pynput handles Right Option cleanly |
| Insertion | NSPasteboard save → set → CGEvent Cmd+V → restore | Exactly what Wispr does; most compatible; keystroke-per-char injection is slow and trips security tools |
| UI | `rumps` menu-bar app | Minimal; shows idle/recording/processing state; quit/toggle |
| Mode | Batch-per-utterance | Wispr's own choice; enables rewrite stage |
| Config | `~/.wisper/config.toml` + `~/.wisper/dictionary.json` | Survives repo moves; simple formats |

## Architecture

```
hold Right Option ──▶ hotkey.py ──start──▶ audio.py (sounddevice, 16 kHz mono)
release            ──▶ hotkey.py ──stop───▶ ndarray
                                              │
                                              ▼
                                         asr.py (parakeet-mlx)
                                              │ raw transcript
                                              ▼
                                    cleanup.py (rules: fillers,
                                    self-corrections, whitespace)
                                              │
                                              ▼
                                    dictionary.py (personal terms)
                                              │
                                              ▼
                              polish.py (optional mlx-lm LLM pass,
                              tone hint from context.py frontmost app)
                                              │ final text
                                              ▼
                                    paste.py (clipboard swap + Cmd+V)

app.py (rumps menu bar) owns threads and state: IDLE → RECORDING → PROCESSING → IDLE
```

## Components

- **`config.py`** — load/merge TOML config with defaults (model names, hotkey, LLM
  on/off, filler list). Pure, testable.
- **`cleanup.py`** — deterministic text rules: strip filler words ("um", "uh",
  "you know" — word-boundary aware, case-insensitive), collapse whitespace,
  handle simple self-corrections on explicit markers. Pure, testable.
- **`dictionary.py`** — user term replacements (e.g. "anurag" spelled correctly,
  project names), case-preserving where sensible. Pure, testable.
- **`audio.py`** — start/stop capture into a numpy array; 16 kHz mono float32.
- **`asr.py`** — lazy-loads Parakeet once, `transcribe(ndarray) -> str`. Falls back
  to mlx-whisper if parakeet-mlx unavailable.
- **`polish.py`** — optional: small instruct model rewrites transcript given a tone
  hint; strict prompt (return only rewritten text); disabled → passthrough.
- **`context.py`** — frontmost app name via NSWorkspace → tone hint
  (chat/email/code/default).
- **`hotkey.py`** — pynput global listener; hold-to-talk semantics with debounce;
  callbacks on_start/on_stop.
- **`paste.py`** — pasteboard save/set/restore + CGEvent Cmd+V; copy-only fallback
  (leave text on clipboard) if paste fails.
- **`app.py`** — rumps app; wires everything; status icon text (🎤 idle, 🔴 rec,
  ⏳ processing); menu: enable/disable, LLM polish toggle, quit.

## Error handling

- ASR/LLM model load failure → log, degrade (LLM off; ASR failure = fatal with
  clear message about first-run model download).
- Empty/too-short audio (<0.3 s) → discard silently.
- Paste failure → text stays on clipboard, menu-bar notification.
- Missing permissions (mic, Accessibility) → detect and print/notify setup steps.

## Testing

- pytest for pure modules: cleanup rules, dictionary, config parsing, polish prompt
  construction (LLM call mocked).
- ASR smoke test with a locally generated known-content audio file (`say` command →
  wav → transcribe → assert keywords).
- Hotkey/paste/menu-bar verified manually — they require user-granted permissions
  (documented in README).

## Out of scope (v1)

Command mode (voice-edit selected text), AX-tree text context around cursor,
screen OCR, streaming preview, multi-language auto-detect (Parakeet v2 is
English-first; model swap is a config change), Windows/Linux, packaging as .app
bundle (runs via `uv run wisper`).

## Privacy property

No network calls at runtime. Models downloaded once from Hugging Face at first
run (or prefetch step), then everything — audio, transcripts, dictionary —
stays on-device. Audio is held in memory only; nothing persisted unless
history is explicitly enabled later.
