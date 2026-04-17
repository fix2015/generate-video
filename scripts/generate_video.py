#!/usr/bin/env python3
"""
Generate TikTok-style vertical videos with voice, captions, and overlays.

Pipeline:
  1. edge-tts: Generate voice + word-level timestamps (FREE)
  2. Pillow: Render background, title, code box, caption frames
  3. FFmpeg: Compose final video (pipes raw frames)
"""

import asyncio
import argparse
import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime

import edge_tts
from PIL import Image, ImageDraw, ImageFont


# ============ DEFAULTS ============
DEFAULT_VOICE = "en-US-GuyNeural"
DEFAULT_WIDTH = 720
DEFAULT_HEIGHT = 1280
DEFAULT_FPS = 30


# ============ COLORS ============
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ============ FONT HELPERS ============
def find_font():
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/Library/Fonts/Arial Black.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for f in candidates:
        if os.path.exists(f):
            return f
    return None


def find_mono_font():
    candidates = [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/SFMono.ttf",
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    for f in candidates:
        if os.path.exists(f):
            return f
    return None


def load_font(path, size):
    try:
        return ImageFont.truetype(path or "", size)
    except Exception:
        return ImageFont.load_default()


# ============ TTS ============
async def generate_voice_with_timestamps(text, audio_path, voice, rate=None, pitch=None):
    kwargs = {"text": text, "voice": voice}
    if rate:
        kwargs["rate"] = rate
    if pitch:
        kwargs["pitch"] = pitch

    try:
        communicate = edge_tts.Communicate(**kwargs, boundary="WordBoundary")
    except TypeError:
        communicate = edge_tts.Communicate(**kwargs)

    word_timings = []
    with open(str(audio_path), "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_timings.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 10_000_000,
                    "duration": chunk["duration"] / 10_000_000,
                })

    if not word_timings:
        word_timings = estimate_word_timings(text, audio_path)

    print(f"  Voice: {voice} ({len(word_timings)} words)")
    return word_timings


def estimate_word_timings(text, audio_path):
    duration = get_audio_duration(str(audio_path))
    words = text.split()
    if not words or duration <= 0:
        return []
    avg = duration / len(words)
    timings, t = [], 0.1
    for word in words:
        wd = avg * 0.8
        timings.append({"text": word, "start": t, "duration": wd})
        pause = avg * 0.2
        if word.rstrip().endswith((".", "?", "!", ",")):
            pause += avg * 0.3
        t += wd + pause
    return timings


def get_audio_duration(audio_path):
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True
    )
    return float(result.stdout.strip()) if result.stdout.strip() else 60


# ============ CAPTIONS ============
def create_caption_chunks(word_timings, words_per_chunk=4):
    chunks, current_words, current_start = [], [], 0
    for i, w in enumerate(word_timings):
        if not current_words:
            current_start = w["start"]
        current_words.append(w["text"])
        is_punct = w["text"].rstrip().endswith((".", "?", "!", ","))
        if len(current_words) >= words_per_chunk or is_punct or i == len(word_timings) - 1:
            end_time = w["start"] + w["duration"] + 0.05
            chunks.append({"text": " ".join(current_words), "start": current_start, "end": end_time})
            current_words = []
    return chunks


def render_caption_image(text, width, height=200):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_font(find_font(), 52)

    words = text.split()
    bbox = draw.textbbox((0, 0), text, font=font)
    full_w = bbox[2] - bbox[0]
    full_h = bbox[3] - bbox[1]

    if full_w > width - 40:
        mid = len(words) // 2
        lines = [" ".join(words[:mid]), " ".join(words[mid:])]
    else:
        lines = [text]

    line_h = full_h + 8
    start_y = (height - line_h * len(lines)) // 2

    for li, line in enumerate(lines):
        lb = draw.textbbox((0, 0), line, font=font)
        lw = lb[2] - lb[0]
        x = (width - lw) // 2
        y = start_y + li * line_h
        # Outline
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx * dx + dy * dy <= 9:
                    draw.text((x + dx, y + dy), line, fill=(0, 0, 0), font=font)
        draw.text((x, y), line, fill=(255, 255, 255), font=font)
    return img


# ============ BACKGROUND FRAME ============
def render_background(width, height, bg_color, accent_color, title=None, code_text=None, logo_path=None):
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    bold_font = load_font(find_font(), 34)
    code_font = load_font(find_mono_font(), 22)

    # Accent bar
    draw.rectangle([0, 0, width, 6], fill=accent_color)

    y_cursor = 20

    # Logo
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((150, 150), Image.LANCZOS)
        img.paste(logo, (30, y_cursor), logo)
        y_cursor += 160

    # Title
    if title:
        y_cursor += 30
        max_w = width - 80
        words = title.split()
        lines, current = [], ""
        for word in words:
            test = f"{current} {word}".strip()
            tb = draw.textbbox((0, 0), test, font=bold_font)
            if tb[2] - tb[0] <= max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        lh = draw.textbbox((0, 0), "Ag", font=bold_font)[3] + 6
        for line in lines:
            lb = draw.textbbox((0, 0), line, font=bold_font)
            lw = lb[2] - lb[0]
            x = max(40, (width - lw) // 2)
            draw.text((x, y_cursor), line, fill=(167, 139, 250), font=bold_font)
            y_cursor += lh
        y_cursor += 20

    # Code box
    if code_text:
        code_box_color = tuple(min(c + 15, 255) for c in bg_color)
        code_box_y = y_cursor + 10
        code_lines = code_text.split("\\n") if "\\n" in code_text else code_text.split("\n")
        code_box_h = len(code_lines) * 30 + 40
        draw.rectangle([40, code_box_y, width - 40, code_box_y + code_box_h], fill=code_box_color)

        cy = code_box_y + 20
        for line in code_lines:
            if line.strip().startswith(("#", "//")):
                color = (148, 163, 184)
            else:
                color = (56, 189, 248)
            draw.text((65, cy), line, fill=color, font=code_font)
            cy += 30

    return img


# ============ VIDEO CREATION ============
def create_video(audio_path, caption_chunks, bg_frame, output_path, width, height, fps, captions_enabled):
    duration = get_audio_duration(audio_path)
    total_frames = int(duration * fps)

    bg_rgb = bg_frame.convert("RGB")

    # Pre-render captions
    caption_images = {}
    if captions_enabled:
        for i, chunk in enumerate(caption_chunks):
            caption_images[i] = render_caption_image(chunk["text"], width)

    def get_caption(t):
        for i, chunk in enumerate(caption_chunks):
            if chunk["start"] <= t <= chunk["end"]:
                return caption_images.get(i)
        return None

    caption_y = int(height * 0.63)

    print(f"  Rendering {total_frames} frames ({duration:.1f}s at {fps}fps)...")

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}", "-r", str(fps),
        "-i", "pipe:0",
        "-i", str(audio_path),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(output_path)
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        for frame_idx in range(total_frames):
            frame = bg_rgb.copy()

            if captions_enabled:
                t = frame_idx / fps
                cap_img = get_caption(t)
                if cap_img:
                    frame.paste(cap_img, (0, caption_y), cap_img)

            proc.stdin.write(frame.tobytes())

            if frame_idx % (fps * 5) == 0 and frame_idx > 0:
                pct = frame_idx / total_frames * 100
                print(f"    {pct:.0f}%")

        proc.stdin.close()
        proc.wait()
    except BrokenPipeError:
        proc.wait()

    if proc.returncode != 0:
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        for line in stderr.split("\n")[-10:]:
            if line.strip():
                print(f"    {line}")
        return False

    print(f"  Video ready: {output_path}")
    return True


# ============ LIST VOICES ============
async def list_voices(lang_filter=None):
    voices = await edge_tts.list_voices()
    if lang_filter:
        lf = lang_filter.lower()
        voices = [v for v in voices if v["Locale"].lower().startswith(lf)]

    if not voices:
        print("No voices found.")
        return

    by_lang = {}
    for v in voices:
        lang = v["Locale"].split("-")[0]
        by_lang.setdefault(lang, []).append(v)

    print(f"\nAvailable voices ({len(voices)} total):\n")
    for lang in sorted(by_lang):
        print(f"  {lang.upper()}:")
        for v in sorted(by_lang[lang], key=lambda x: x["ShortName"]):
            print(f"    {v['ShortName']:40s} {v.get('Gender', ''):8s} {v['Locale']}")
        print()


# ============ MAIN ============
def main():
    parser = argparse.ArgumentParser(description="Generate TikTok-style video from text")
    parser.add_argument("--text", type=str, help="Text for voiceover")
    parser.add_argument("--voice", type=str, default=DEFAULT_VOICE)
    parser.add_argument("--output", type=str, help="Output video path")
    parser.add_argument("--title", type=str, help="Title overlay")
    parser.add_argument("--code", type=str, help="Code overlay text")
    parser.add_argument("--logo", type=str, help="Logo image path")
    parser.add_argument("--audio", type=str, help="Use existing audio file")
    parser.add_argument("--rate", type=str, help="TTS speech rate")
    parser.add_argument("--pitch", type=str, help="TTS voice pitch")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS)
    parser.add_argument("--bg-color", type=str, default="0f172a")
    parser.add_argument("--accent-color", type=str, default="7c3aed")
    parser.add_argument("--no-captions", action="store_true")
    parser.add_argument("--list-voices", action="store_true")
    parser.add_argument("--lang", type=str, help="Filter voices by language")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list_voices:
        asyncio.run(list_voices(args.lang))
        return

    if not args.text:
        parser.print_help()
        sys.exit(1)

    bg_color = hex_to_rgb(args.bg_color)
    accent_color = hex_to_rgb(args.accent_color)

    # Auto-generate output name
    output = args.output
    if not output:
        slug = re.sub(r'[^a-z0-9]+', '_', args.text[:30].lower()).strip('_')
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"{ts}_{slug}.mp4"

    if args.dry_run:
        print(f"\n  DRY RUN — would generate:")
        print(f"  Text:    {args.text[:80]}...")
        print(f"  Voice:   {args.voice}")
        print(f"  Title:   {args.title or '(none)'}")
        print(f"  Code:    {args.code[:50] + '...' if args.code and len(args.code) > 50 else args.code or '(none)'}")
        print(f"  Logo:    {args.logo or '(none)'}")
        print(f"  Audio:   {args.audio or '(TTS generated)'}")
        print(f"  Size:    {args.width}x{args.height} @ {args.fps}fps")
        print(f"  BG:      #{args.bg_color}")
        print(f"  Accent:  #{args.accent_color}")
        print(f"  Captions: {'off' if args.no_captions else 'on'}")
        print(f"  Output:  {output}\n")
        return

    # Step 1: Audio
    audio_path = args.audio
    word_timings = []

    if not audio_path:
        print("Step 1: Generating voice...")
        audio_path = output.replace(".mp4", ".mp3")
        word_timings = asyncio.run(
            generate_voice_with_timestamps(args.text, audio_path, args.voice, args.rate, args.pitch)
        )
    else:
        print(f"Step 1: Using existing audio: {audio_path}")
        word_timings = estimate_word_timings(args.text, audio_path)

    # Step 2: Captions
    caption_chunks = []
    if not args.no_captions:
        print("Step 2: Creating captions...")
        caption_chunks = create_caption_chunks(word_timings)
        print(f"  {len(caption_chunks)} caption chunks")
    else:
        print("Step 2: Captions disabled")

    # Step 3: Background
    print("Step 3: Rendering background...")
    bg_frame = render_background(
        args.width, args.height, bg_color, accent_color,
        title=args.title, code_text=args.code, logo_path=args.logo,
    )

    # Step 4: Compose video
    print("Step 4: Creating video...")
    success = create_video(
        audio_path, caption_chunks, bg_frame, output,
        args.width, args.height, args.fps,
        captions_enabled=not args.no_captions,
    )

    if success:
        size_mb = Path(output).stat().st_size / 1024 / 1024
        print(f"\n  Video: {output} ({size_mb:.1f} MB)\n")
    else:
        print("\n  Failed. Check FFmpeg errors above.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
