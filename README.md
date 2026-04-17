# generate-video

> Generate TikTok-style videos with voice, captions, and code overlays from text — one command.

[![npm version](https://img.shields.io/npm/v/generate-video.svg)](https://www.npmjs.com/package/generate-video)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Free TTS, animated captions, code overlays, custom colors. No API key needed.

## Quick Start

```bash
npx generate-video "JavaScript closures explained in 30 seconds"
```

Outputs a vertical `.mp4` video (720x1280) with voiceover and animated captions.

## Prerequisites

- **Node.js** >= 14
- **Python 3** with pip (edge-tts + Pillow auto-install on first run)
- **FFmpeg** installed (`brew install ffmpeg` / `apt install ffmpeg`)

## Usage

### Basic video

```bash
npx generate-video "Your script text here"
```

### With title and code overlay

```bash
npx generate-video "Closures capture variables from outer scope" \
  --title "Closures 101" \
  --code "function outer() {\n  let x = 10;\n  return () => x;\n}"
```

### Custom voice

```bash
npx generate-video "Bonjour le monde" --voice fr-FR-HenriNeural
npx generate-video "Hello world" --voice en-GB-SoniaNeural
```

### Adjust speed and pitch

```bash
npx generate-video "Fast narration" --rate "+30%"
npx generate-video "Deep voice" --pitch "-5Hz"
```

### Custom output file

```bash
npx generate-video "Your text" --output my-video.mp4
```

### With logo

```bash
npx generate-video "Your text" --logo ./my-logo.png
```

### Use existing audio

```bash
npx generate-video "Caption text for sync" --audio ./voiceover.mp3
```

### Custom colors

```bash
npx generate-video "Your text" --bg-color 1a1a2e --accent-color e94560
```

### Custom dimensions

```bash
# Landscape (YouTube)
npx generate-video "Your text" --width 1920 --height 1080

# Square (Instagram)
npx generate-video "Your text" --width 1080 --height 1080
```

### Disable captions

```bash
npx generate-video "Your text" --no-captions
```

### Preview without generating

```bash
npx generate-video "Your text" --dry-run
```

### Browse voices

```bash
npx generate-video --voices
npx generate-video --voices --lang en
npx generate-video --voices --lang fr
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
| `-r, --rate <rate>` | Speech rate (`+20%`, `-10%`) | Normal |
| `-p, --pitch <pitch>` | Voice pitch (`+5Hz`) | Normal |
| `--width <px>` | Video width | `720` |
| `--height <px>` | Video height | `1280` |
| `--fps <n>` | Frames per second | `30` |
| `--bg-color <hex>` | Background color | `0f172a` |
| `--accent-color <hex>` | Accent bar color | `7c3aed` |
| `--no-captions` | Disable captions | — |
| `--voices` | List TTS voices | — |
| `-l, --lang <code>` | Filter voices | — |
| `--dry-run` | Preview only | — |

## How It Works

1. **edge-tts** generates voice audio with word-level timestamps (free Microsoft TTS)
2. **Pillow** renders the background frame with title, code box, and logo
3. **Pillow** renders animated caption frames synced to word timings
4. **FFmpeg** composites everything into a final video (piped raw frames)

## License

MIT
