# Wisper

A private, fully-local [Wispr Flow](https://wisprflow.ai) clone for macOS.
Hold a key, speak, release — cleaned-up text is pasted into whatever app has
focus. **Zero network calls at runtime.** Audio, transcripts, and your personal
dictionary never leave your machine.

## How it works

```
hold Right Option → record mic (16 kHz)
release           → Parakeet TDT 0.6B (MLX, Apple Silicon)   ~0.9 s
                  → rule cleanup (fillers, whitespace, dictionary)
                  → Qwen2.5-1.5B 4-bit polish (tone, self-corrections)  ~0.5 s
                  → clipboard-swap paste (save → set → ⌘V → restore)
```

Same pipeline shape as Wispr Flow (batch-per-utterance ASR → LLM rewrite →
clipboard paste), but the cloud GPUs are replaced by MLX models on your Mac.

Example, spoken into an email: *"um so basically can you send the report on
tuesday, no wait, wednesday"* → **"Can you send the report by Wednesday?"**

Tone adapts to the frontmost app: casual in Slack/Messages, professional in
Mail, verbatim-technical in editors/terminals.

## Setup

Requires Apple Silicon, macOS 14+, and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run wisper
```

First run downloads the two models from Hugging Face (~1.5 GB total) into the
standard HF cache; after that it is fully offline.

### Permissions (one-time)

Grant these to your terminal app (or whatever launches `wisper`) in
**System Settings → Privacy & Security**:

- **Microphone** — to record your speech
- **Accessibility** — for the global hotkey listener and the ⌘V paste keystroke

Restart `wisper` after granting.

## Usage

- Menu-bar icon: 🎤 idle · 🔴 recording · ⏳ processing · … loading models
- **Hold Right Option**, speak, release. Text pastes at your cursor.
- Menu: toggle dictation on/off, toggle the LLM polish pass, quit.
- Utterances shorter than 0.3 s are discarded.
- If pasting fails (secure fields, some remote desktops), the text is left on
  the clipboard — paste manually.

## Configuration

Optional files in `~/.wisper/`:

`config.toml`
```toml
asr_backend = "parakeet"     # "parakeet" (fast, English) or "whisper" (multilingual)
asr_model = "mlx-community/parakeet-tdt-0.6b-v2"
whisper_model = "mlx-community/whisper-large-v3-turbo"
polish_languages = ["en"]    # LLM polish only runs for these; others get rules-only
llm_model = "mlx-community/Qwen2.5-1.5B-Instruct-4bit"
llm_polish = true
llm_backend = "mlx"     # "mlx" (in-process, default) or "ollama" (local daemon)
ollama_model = "llama3.2"
ollama_url = "http://localhost:11434"
hotkey = "alt_r"        # alt_r, alt_l, cmd_r, ctrl_r, f13
min_utterance_seconds = 0.3
filler_words = ["um", "uh", "erm", "you know", "i mean"]
```

`dictionary.json` — spoken form → written form, applied case-insensitively:
```json
{ "anurag": "Anurag", "wisper": "Wisper", "java script": "JavaScript" }
```

## Development

```sh
uv run pytest        # 30 tests: cleanup rules, dictionary, config, polish, context
```

Design doc: [docs/superpowers/specs/2026-07-02-local-wispr-clone-design.md](docs/superpowers/specs/2026-07-02-local-wispr-clone-design.md)

| Module | Responsibility |
|---|---|
| `audio.py` | mic capture via sounddevice |
| `asr.py` | Parakeet (English) or Whisper (multilingual) MLX transcription |
| `cleanup.py` | deterministic filler/whitespace rules |
| `dictionary.py` | personal term replacements |
| `polish.py` | optional local-LLM rewrite with tone hint (mlx-lm or Ollama backend) |
| `context.py` | frontmost app → tone |
| `hotkey.py` | pynput push-to-talk |
| `paste.py` | clipboard-swap ⌘V insertion |
| `app.py` | rumps menu bar + pipeline orchestration |

## Multilingual dictation

Set `asr_backend = "whisper"` for 100+ languages (incl. Hindi/Hinglish) with
per-utterance auto-detection — speak whichever language you like, no switching.
Whisper is ~2x slower than Parakeet on short utterances (~1.8 s vs ~0.9 s).
Non-English utterances skip the LLM polish (rules-only cleanup) unless you add
their codes to `polish_languages`.

## Not implemented (vs Wispr Flow)

Command mode (voice-editing selected text), text context around the cursor,
screen OCR, streaming preview, Windows/Linux.
