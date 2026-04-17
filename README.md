# generate-video

> Generate TikTok-style videos with voice, captions, avatar, and code overlays — one command.

[![npm version](https://img.shields.io/npm/v/generate-video.svg)](https://www.npmjs.com/package/generate-video)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Free TTS, animated captions, lip-synced avatar, preview intro, built-in script bank. No API key needed.

## Quick Start

```bash
npx generate-video "JavaScript closures explained in 30 seconds"
```

## Features

- **Voice** — 400+ TTS voices via edge-tts (free, unlimited)
- **Captions** — word-synced animated captions with outline
- **Avatar** — lip-synced cartoon avatar (amplitude analysis)
- **Preview** — branded 1.5s intro frame
- **Code overlay** — syntax-highlighted code box
- **Title overlay** — centered, word-wrapped
- **Logo** — custom PNG in top-left
- **Script bank** — 12 built-in topics (RAG, JS, etc.)
- **Custom colors** — background, accent
- **Custom dimensions** — vertical, landscape, square

## Prerequisites

- **Node.js** >= 14
- **Python 3** with pip (auto-installs edge-tts + Pillow)
- **FFmpeg** (`brew install ffmpeg` / `apt install ffmpeg`)

## Usage

### Basic video

```bash
npx generate-video "Your script text here"
```

### With all features

```bash
npx generate-video "Your text" \
  --title "My Video" \
  --code "const x = 42;" \
  --avatar \
  --preview \
  --logo ./logo.png
```

### Built-in topics

```bash
# List all topics
npx generate-video --topics

# Generate from a built-in topic
npx generate-video --topic 0
npx generate-video --topic 5 --avatar --preview
```

### Avatar (lip-sync)

```bash
npx generate-video "Your text" --avatar
```

Generates a cartoon avatar with 4 mouth positions synced to audio amplitude.

### Preview intro frame

```bash
npx generate-video "Your text" --title "My Video" --preview
npx generate-video "Your text" --preview --preview-bg ./background.png
npx generate-video "Your text" --preview --preview-duration 2.0
```

Adds a branded intro frame before the main content. Audio is delayed to sync.

### Voice options

```bash
npx generate-video "Bonjour" --voice fr-FR-HenriNeural
npx generate-video "Fast speech" --rate "+30%"
npx generate-video "Deep voice" --pitch "-5Hz"
npx generate-video --voices --lang en
```

### Custom look

```bash
npx generate-video "Your text" --bg-color 1a1a2e --accent-color e94560
npx generate-video "Your text" --width 1920 --height 1080   # Landscape
npx generate-video "Your text" --width 1080 --height 1080   # Square
```

### Use existing audio

```bash
npx generate-video "Caption text" --audio ./voiceover.mp3
```

### Preview without generating

```bash
npx generate-video "Your text" --dry-run
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-v, --voice <name>` | TTS voice | `en-US-GuyNeural` |
| `-o, --output <file>` | Output path | Auto-generated |
| `-t, --title <text>` | Title overlay | — |
| `-c, --code <text>` | Code box overlay | — |
| `--logo <path>` | Logo image (PNG) | — |
| `--audio <path>` | Existing audio file | — |
| `-r, --rate <rate>` | Speech rate | Normal |
| `-p, --pitch <pitch>` | Voice pitch | Normal |
| `--avatar` | Enable lip-synced avatar | off |
| `--preview` | Add preview intro frame | off |
| `--preview-bg <path>` | Preview background image | — |
| `--preview-duration <s>` | Preview duration | `1.5` |
| `--topic <index>` | Use built-in topic | — |
| `--topics` | List built-in topics | — |
| `--width <px>` | Video width | `720` |
| `--height <px>` | Video height | `1280` |
| `--fps <n>` | Frames per second | `30` |
| `--bg-color <hex>` | Background color | `0f172a` |
| `--accent-color <hex>` | Accent color | `7c3aed` |
| `--no-captions` | Disable captions | — |
| `--voices` | List TTS voices | — |
| `-l, --lang <code>` | Filter voices | — |
| `--dry-run` | Preview only | — |

## How It Works

1. **edge-tts** generates voice audio with word-level timestamps (free)
2. **Pillow** renders background frame with title, code box, logo
3. **Pillow** renders animated caption frames synced to word timings
4. **Pillow** generates avatar with 4 mouth states (closed, small, medium, wide)
5. **FFmpeg** analyzes audio amplitude for lip-sync
6. **FFmpeg** composites frames + audio into final video

## License

MIT
