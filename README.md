<div align="center">

# 🪄 Accio

**Hold a key, talk, and clean text appears — without your voice ever leaving your Mac.**

A private, fully-local voice dictation app for macOS. Push-to-talk dictation with
on-device speech recognition and LLM cleanup — an independent, offline take on the
[Wispr Flow](https://wisprflow.ai) experience.

[![macOS](https://img.shields.io/badge/macOS-14+-000000?logo=apple&logoColor=white)](https://www.apple.com/macos/)
[![Apple Silicon](https://img.shields.io/badge/Apple_Silicon-M1–M4-333333?logo=apple&logoColor=white)](https://support.apple.com/en-us/116943)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-53_passing-3ecf8e)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[![On-device](https://img.shields.io/badge/On--device-Whisper_·_Parakeet_·_MLX-7c5cff)](https://github.com/ml-explore/mlx)
[![Network calls](https://img.shields.io/badge/network_calls-zero-000000)](#privacy)
[![Languages](https://img.shields.io/badge/languages-English_·_Hinglish-orange)](#multilingual-dictation)

<br>

*"Your voice is yours. Accio keeps it that way."*

**push-to-talk · on-device speech + LLM cleanup · English + Hinglish · nothing leaves your Mac · free & open source**

<br>

[Why](#why-accio) · [How It Works](#how-it-works) · [Features](#features) · [Quick Start](#quick-start) · [Privacy](#privacy)

</div>

<!-- TODO before launch: record a ~20s demo GIF and drop it here.
     Money shot: dictate, then toggle Wi-Fi OFF and dictate again — still works. -->

---

```
        RECORD                    UNDERSTAND                    INSERT
   ┌────────────────┐        ┌────────────────┐        ┌────────────────┐
   │  Hold a key,   │        │  Whisper /     │        │  Clean text     │
   │  speak into    │───────▶│  Parakeet ASR  │───────▶│  pasted at your │
   │  any text field│        │  + LLM cleanup │        │  cursor (⌘V)    │
   │  (push-to-talk)│        │  → on your Mac │        │  clipboard-safe │
   └────────────────┘        └────────────────┘        └────────────────┘
      release to stop          fillers removed,            restores your
     16 kHz mono audio        self-corrections fixed      clipboard after

                          nothing leaves your machine
```

---

## Why Accio

You've probably seen the Wispr Flow ad — it's everywhere. It's a lovely dictation
app: hold a key, talk, clean text appears in any app. But every word you speak is
uploaded to their cloud, there's a 2,000-words-a-week free cap before $15/month,
and you need an account.

**Accio does the same thing, entirely on your Mac.** The speech model *and* the
language model that cleans up your "ums" both run on Apple Silicon. No cloud, no
account, no API keys — pull your Wi-Fi mid-sentence and it still works. It even
speaks Hinglish, which the cloud apps don't.

Same interaction, opposite privacy model. Free and open source.

---

## How It Works

```
1. RECORD      Hold Right Option → the mic records while you talk (16 kHz
               mono, in memory). Release to stop. A menu-bar icon shows
               idle / recording / processing.

2. UNDERSTAND  A single worker (all MLX inference on one thread) runs:
               Whisper or Parakeet for transcription → rule cleanup (fillers,
               whitespace, your personal dictionary) → a small local LLM that
               fixes punctuation, tone, and self-corrections. Tone adapts to
               the frontmost app (casual in Slack, formal in Mail).

3. INSERT      The final text is pasted at your cursor the way Wispr does it:
               save the clipboard → set the text → synthesize ⌘V → restore
               your clipboard. Works in any text field.
```

Batch-per-utterance (not streaming) — waiting for the full sentence is what lets
the LLM rewrite it. End-to-end ~2s on an M4.

Example, spoken into an email: *"um so basically can you send the report on
tuesday, no wait, wednesday"* → **"Can you send the report by Wednesday?"**

---

## Features

| | Feature | Detail |
|---|---|---|
| 🔒 | **100% on-device** | Speech recognition and LLM cleanup both run locally via Apple MLX. Zero network calls at runtime — unplug your Wi-Fi and it still works. |
| 🎙️ | **Push-to-talk** | Hold Right Option (configurable), speak, release. Text lands wherever your cursor is — Slack, Mail, editors, any field. |
| ✨ | **LLM cleanup** | Removes fillers, fixes punctuation, and applies self-corrections — *"Tuesday, no wait Wednesday"* becomes *"Wednesday."* Tone adapts per app. |
| 🌏 | **English + Hinglish** | Auto-detects language per sentence. Hindi comes out as romanized Hinglish (*"kal meeting teen baje hai"*), never Devanagari, never translated. |
| 📖 | **Personal dictionary** | Teach it names and terms it mishears — a simple `spoken → written` map. |
| 🚀 | **Launch at login** | `accio install` deploys a background agent + a Spotlight-searchable **Accio.app**. Type "Accio" to summon it. |
| 🆓 | **Free & open source** | MIT licensed. Unlimited words, no account, no telemetry. |

### Accio vs Wispr Flow

|                       | Accio        | Wispr Flow                    |
| --------------------- | ------------ | ----------------------------- |
| Where your audio goes | Stays on Mac | Uploaded to their cloud       |
| Price                 | Free         | $15/mo after 2,000 words/week |
| Works offline         | ✅ Yes       | ❌ No (cloud ASR)             |
| Account required      | ❌ No        | ✅ Yes                        |
| Hindi → Hinglish      | ✅ Yes       | Devanagari                    |
| Source available      | ✅ MIT       | ❌ Closed                     |

---

## Quick Start

**Requirements:** Apple Silicon Mac, macOS 14+, and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/anuragmerndev/accio-ai.git
cd accio-ai
uv sync
uv run accio
```

First run downloads the models from Hugging Face (~1.5 GB) into the standard HF
cache; after that it is fully offline.

### Permissions (one-time)

Grant these to your terminal (or whatever launches `accio`) in **System Settings
→ Privacy & Security**:

- **Microphone** — to record your speech
- **Input Monitoring** — to *receive* the global hotkey (the app requests this on
  launch and registers itself in the list; just toggle it on)
- **Accessibility** — to *send* the ⌘V paste keystroke

Input Monitoring and Accessibility are separate permissions — the first lets the
app hear your hotkey, the second lets it paste. You need both. Restart after
granting.

### Launch at login

```bash
uv run accio install     # start at every login + create Spotlight Accio.app
uv run accio uninstall   # stop doing so
uv run accio start        # (re)start now, no logout needed
uv run accio stop         # stop until next login / start
```

Because a repo under `~/Desktop` is shielded from background agents by macOS,
`install` deploys a self-contained copy to `~/Library/Application Support/accio`
and points a LaunchAgent there. Re-run `install` after code changes.

---

## Configuration

Optional files in `~/.accio/`:

`config.toml`
```toml
asr_backend = "parakeet"     # "parakeet" (fast, English) or "whisper" (multilingual)
asr_model = "mlx-community/parakeet-tdt-0.6b-v2"
whisper_model = "mlx-community/whisper-large-v3-turbo"
polish_languages = ["en"]    # LLM polish only runs for these
romanize_languages = []      # e.g. ["hi"] pastes Hindi as romanized Hinglish (via Ollama)
romanize_model = "llama3.2"
llm_model = "mlx-community/Qwen2.5-1.5B-Instruct-4bit"
llm_polish = true
llm_backend = "mlx"          # "mlx" (in-process, default) or "ollama" (local daemon)
hotkey = "alt_r"             # alt_r, alt_l, cmd_r, ctrl_r, f13
```

### Personal dictionary — teach it your names and terms

`~/.accio/dictionary.json` maps what the model *hears* → what you *want written*,
as whole words, case-insensitively. This fixes proper nouns the ASR mangles —
Whisper hears the uncommon word "Accio" as "Akio" or "Aqio", so map the
mishearings to the right spelling:

```json
{
  "akio": "Accio",
  "aqio": "Accio",
  "anurag": "Anurag",
  "java script": "JavaScript"
}
```

Build your library over time: when a name comes out wrong, add the wrong spelling
on the left and the correct one on the right, then restart.

---

## Multilingual dictation

Set `asr_backend = "whisper"` for 100+ languages (incl. Hindi/Hinglish) with
per-utterance auto-detection — speak whichever language you like, no switching.
Whisper is ~2x slower than Parakeet on short utterances (~1.8 s vs ~0.9 s).

With `romanize_languages = ["hi"]`, Hindi output is converted from Devanagari to
natural romanized Hinglish (*"कल मीटिंग तीन बजे है"* → *"kal meeting teen baje
hai"*) by a local LLM via Ollama — same words, Latin script, never translated.

---

## Privacy

No network calls at runtime. Models download once from Hugging Face on first run,
then everything — audio, transcripts, your dictionary — stays on-device. Audio is
held in memory only and never persisted. There is no account, no server, and no
telemetry. The only optional local dependency is [Ollama](https://ollama.com) on
`localhost` for Hinglish romanization.

---

## Architecture

![Architecture](docs/accio-architecture.drawio.png)

| Module | Responsibility |
|---|---|
| `audio.py` | mic capture via sounddevice |
| `asr.py` | Parakeet (English) or Whisper (multilingual) MLX transcription |
| `cleanup.py` | deterministic filler / whitespace rules |
| `dictionary.py` | personal term replacements |
| `polish.py` | optional local-LLM rewrite with tone hint (mlx-lm or Ollama) |
| `context.py` | frontmost app → tone |
| `hotkey.py` | pynput push-to-talk |
| `paste.py` | clipboard-swap ⌘V insertion |
| `pipeline.py` | single worker thread; all MLX inference on one thread |
| `app.py` | rumps menu bar + orchestration + watchdog |

### Development

```bash
uv run pytest          # 53 tests
```

Design doc:
[docs/superpowers/specs/2026-07-02-local-wispr-clone-design.md](docs/superpowers/specs/2026-07-02-local-wispr-clone-design.md)

---

## Credits

Built on the open-source ecosystem that makes local speech possible:
[parakeet-mlx](https://github.com/senstella/parakeet-mlx) and
[mlx-whisper](https://github.com/ml-explore/mlx-examples) for ASR,
[mlx-lm](https://github.com/ml-explore/mlx-lm) and [Ollama](https://ollama.com)
for the polish/romanize passes, and [rumps](https://github.com/jaredks/rumps) for
the menu bar. Design inspired by [VoiceInk](https://github.com/Beingpax/VoiceInk)
and [Handy](https://github.com/cjpais/handy).

## Disclaimer

Accio is an independent, from-scratch reimplementation for personal use. It is
**not affiliated with, endorsed by, or derived from Wispr Flow or Wispr AI** —
"Wispr Flow" is referenced only to describe the interaction model this project
reproduces locally.

## License

[MIT](LICENSE) © 2026 anuragmerndev
