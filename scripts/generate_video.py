#!/usr/bin/env python3
"""
Generate TikTok-style vertical videos with voice, captions, avatar, and overlays.

Pipeline:
  1. edge-tts: Generate voice + word-level timestamps (FREE)
  2. Pillow: Render background, title, code box, caption frames, avatar
  3. FFmpeg: Compose final video (pipes raw frames)
"""

import asyncio
import argparse
import math
import os
import re
import struct
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


# ============ BUILT-IN SCRIPT BANK ============
SCRIPTS = [
    {
        "title": "What Is RAG?",
        "hook": "Your AI is lying to you. RAG fixes that.",
        "script": "RAG stands for Retrieval Augmented Generation. Instead of relying on what the model memorized during training, you give it real documents to read before answering. Step one: user asks a question. Step two: you search your knowledge base for relevant chunks. Step three: you feed those chunks plus the question to the LLM. The model answers based on YOUR data, not its imagination. That's RAG in 30 seconds.",
        "code": "# RAG Pipeline\n1. User asks question\n2. Search vector DB\n3. Retrieve relevant chunks\n4. Feed chunks + question to LLM\n5. LLM answers from YOUR data",
        "hashtags": "#ai #rag #llm #machinelearning #coding"
    },
    {
        "title": "RAG vs Fine-Tuning",
        "hook": "Everyone says fine-tune your model. Most of the time RAG is better.",
        "script": "Fine-tuning changes the model's weights. It's expensive, slow, and the model can still hallucinate. RAG keeps the model as is but gives it a cheat sheet at query time. Fine-tuning is like studying for months. RAG is like bringing your notes to the exam. RAG is cheaper, faster to update, and your data stays private.",
        "code": "Fine-tuning:\n  Cost: $$$\n  Update: retrain model\n  Risk: catastrophic forgetting\n\nRAG:\n  Cost: $\n  Update: add new docs\n  Risk: retrieval quality",
        "hashtags": "#ai #rag #finetuning #llm"
    },
    {
        "title": "Why RAG Hallucinates",
        "hook": "You added RAG and your AI STILL lies? Here's why.",
        "script": "RAG doesn't magically fix hallucinations. If your chunks are too big, the model ignores important details. If your chunks are too small, it loses context. If your embeddings are bad, you retrieve the wrong documents entirely. And here's the sneaky one: the model might ignore your retrieved context and answer from memory anyway. Fix it by adding explicit instructions: only answer from the provided context.",
        "code": "# Why RAG still hallucinates\n\n1. Bad chunking strategy\n2. Wrong docs retrieved\n3. Model ignores context\n4. Embedding model mismatch\n5. No 'I don't know' fallback",
        "hashtags": "#ai #rag #hallucination #debugging"
    },
    {
        "title": "Chunking Strategy Matters",
        "hook": "Your RAG is only as good as your chunks.",
        "script": "Chunking is how you split documents before storing them. Too big and the model drowns in irrelevant text. Too small and it loses context. The sweet spot? 200 to 500 tokens with 50 token overlap. But here's the real trick: don't split mid-sentence. Use semantic chunking. Split at paragraph or section boundaries. Even better, add metadata like the document title and section header to each chunk.",
        "code": "# Bad chunking\nchunk = text[0:500]  # random split\n\n# Good chunking\nsplitter = RecursiveCharacterTextSplitter(\n  chunk_size=400,\n  chunk_overlap=50,\n  separators=['\\n\\n', '\\n', '. ']\n)",
        "hashtags": "#ai #rag #chunking #nlp"
    },
    {
        "title": "Vector Databases Explained",
        "hook": "Vector databases are the backbone of every RAG system.",
        "script": "A vector database stores text as numbers. You convert your documents into embeddings, arrays of numbers that capture meaning. Similar meanings get similar numbers. When a user asks a question, you convert it to an embedding too, then find the closest matches in the database. That's semantic search. Popular options: Pinecone for managed, ChromaDB for local, Weaviate for self-hosted.",
        "code": "import chromadb\n\nclient = chromadb.Client()\ncol = client.create_collection('docs')\n\ncol.add(\n  documents=['AI is cool'],\n  ids=['doc1']\n)\n\nresults = col.query(\n  query_texts=['what is AI?']\n)",
        "hashtags": "#ai #vectordb #rag #embeddings"
    },
    {
        "title": "Embeddings Are Everything",
        "hook": "Bad embeddings equals bad RAG. Period.",
        "script": "Embeddings convert text into vectors that capture semantic meaning. The embedding model you choose determines if your RAG finds the right documents. OpenAI's text-embedding-3-small is cheap and good. For better accuracy, use Cohere embed v3 or BGE large. For local and free, use sentence-transformers. Pro tip: always test your embeddings with real queries before building the full pipeline.",
        "code": "# Embedding models ranked\n\n1. Cohere embed-v3 (best)\n2. OpenAI text-embedding-3\n3. BGE-large-en (open source)\n4. all-MiniLM-L6 (fast+free)\n\n# Test retrieval FIRST",
        "hashtags": "#ai #embeddings #rag #nlp"
    },
    {
        "title": "RAG in 10 Lines of Python",
        "hook": "Build a working RAG system in 10 lines of Python.",
        "script": "You don't need a framework. Import ChromaDB. Create a collection. Add your documents. Query with a question. Get the top results. Pass them to an LLM with the question. Done. Ten lines. No LangChain, no LlamaIndex, no complexity. Start here, understand how it works, then add frameworks if you need them.",
        "code": "import chromadb, openai\n\ndb = chromadb.Client()\ncol = db.create_collection('docs')\ncol.add(\n  documents=my_docs, ids=my_ids\n)\nhits = col.query(\n  query_texts=[question], n=3\n)\ncontext = '\\n'.join(hits['documents'][0])\nanswer = openai.chat(context + question)",
        "hashtags": "#ai #rag #python #coding"
    },
    {
        "title": "Hybrid Search Beats Vector",
        "hook": "Pure vector search misses things. Hybrid search fixes it.",
        "script": "Vector search finds semantically similar content but misses exact keyword matches. Someone searches for error code E-4012 and vector search returns vaguely related errors. BM25 keyword search finds exact matches but misses synonyms. Hybrid search combines both: run vector search AND keyword search, then merge the results. Every production RAG system should use hybrid search.",
        "code": "# Hybrid Search\n\n# Vector: semantic similarity\nresults_v = vector_search(query)\n\n# BM25: keyword matching\nresults_k = bm25_search(query)\n\n# Combine with Reciprocal Rank\nfinal = reciprocal_rank_fusion(\n  results_v, results_k\n)",
        "hashtags": "#ai #rag #search #hybrid"
    },
    {
        "title": "Reranking Is the Secret Sauce",
        "hook": "The one trick that makes every RAG system 40% better.",
        "script": "Your vector search returns 20 chunks. Some are great, some are noise. A reranker is a second model that scores each chunk specifically for your query. It's more accurate than embedding similarity because it sees the query and document together. Use Cohere Rerank or BGE Reranker. Retrieve 20 chunks with vector search, rerank them, keep the top 5. This single step improves answer quality by 30 to 40 percent.",
        "code": "# Without reranking\nchunks = vector_search(query, top_k=5)\n# Some irrelevant chunks slip in\n\n# With reranking\nchunks = vector_search(query, top_k=20)\nreranked = reranker.rank(\n  query, chunks\n)\ntop_chunks = reranked[:5]\n# Much better results!",
        "hashtags": "#ai #rag #reranking #optimization"
    },
    {
        "title": "JavaScript Closures",
        "hook": "Closures are the most misunderstood concept in JavaScript.",
        "script": "A closure is a function that remembers the variables from the place where it was created, even after that outer function has finished running. Every time you use a callback, an event handler, or return a function from another function, you're using closures. The inner function closes over the outer function's variables. That's why it's called a closure.",
        "code": "function createCounter() {\n  let count = 0;\n  return function() {\n    count++;\n    return count;\n  };\n}\n\nconst counter = createCounter();\ncounter(); // 1\ncounter(); // 2\ncounter(); // 3",
        "hashtags": "#javascript #closures #coding #webdev"
    },
    {
        "title": "Event Loop Explained",
        "hook": "JavaScript is single-threaded. So how does async work?",
        "script": "JavaScript has one thread but it never blocks. The event loop is the secret. When you call setTimeout or fetch, the browser handles the waiting. When it's done, the callback goes into a queue. The event loop checks: is the call stack empty? If yes, it takes the next callback from the queue and runs it. That's why a setTimeout of zero milliseconds doesn't run immediately. It waits for the stack to clear.",
        "code": "console.log('1');\n\nsetTimeout(() => {\n  console.log('2');\n}, 0);\n\nPromise.resolve().then(() => {\n  console.log('3');\n});\n\nconsole.log('4');\n\n// Output: 1, 4, 3, 2",
        "hashtags": "#javascript #eventloop #async #coding"
    },
    {
        "title": "Promise vs Async Await",
        "hook": "Promises and async await do the same thing. Or do they?",
        "script": "Promises use dot then chains. Async await uses regular looking code. Under the hood, async await IS promises. The await keyword pauses the function until the promise resolves. But here's the key difference: error handling. With promises you chain dot catch. With async await you use try catch blocks. Async await is easier to read, especially when you have multiple sequential async operations.",
        "code": "// Promise chain\nfetch(url)\n  .then(res => res.json())\n  .then(data => process(data))\n  .catch(err => handle(err));\n\n// Async/await\nasync function getData() {\n  try {\n    const res = await fetch(url);\n    const data = await res.json();\n    return process(data);\n  } catch (err) {\n    handle(err);\n  }\n}",
        "hashtags": "#javascript #promises #async #await"
    },
]


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


# ============ AVATAR ============
def generate_avatar_frames(width=300, height=400):
    """Generate 4 avatar frames (closed, small, medium, wide mouth) using Pillow."""
    frames = {}
    mouth_openings = {"closed": 0, "small": 8, "medium": 18, "wide": 30}

    for state, mouth_h in mouth_openings.items():
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx, cy = width // 2, height // 2 - 20

        # Head (circle)
        head_r = 100
        draw.ellipse([cx - head_r, cy - head_r, cx + head_r, cy + head_r],
                     fill=(255, 220, 185), outline=(200, 170, 140), width=3)

        # Eyes
        eye_y = cy - 25
        for ex in [cx - 35, cx + 35]:
            draw.ellipse([ex - 12, eye_y - 15, ex + 12, eye_y + 15],
                         fill=(255, 255, 255), outline=(100, 100, 100), width=2)
            draw.ellipse([ex - 6, eye_y - 8, ex + 6, eye_y + 8],
                         fill=(60, 60, 60))
            draw.ellipse([ex - 2, eye_y - 5, ex + 2, eye_y - 1],
                         fill=(255, 255, 255))

        # Eyebrows
        for ex in [cx - 35, cx + 35]:
            draw.arc([ex - 18, eye_y - 35, ex + 18, eye_y - 15],
                     start=200, end=340, fill=(80, 60, 40), width=3)

        # Nose
        draw.polygon([(cx, cy + 5), (cx - 8, cy + 20), (cx + 8, cy + 20)],
                     fill=(240, 200, 170))

        # Mouth
        mouth_y = cy + 40
        if mouth_h == 0:
            # Closed - slight smile
            draw.arc([cx - 25, mouth_y - 10, cx + 25, mouth_y + 10],
                     start=10, end=170, fill=(180, 80, 80), width=3)
        else:
            # Open mouth
            draw.ellipse([cx - 22, mouth_y - mouth_h // 2, cx + 22, mouth_y + mouth_h // 2],
                         fill=(180, 50, 50), outline=(140, 40, 40), width=2)
            # Teeth hint for wide
            if mouth_h > 15:
                draw.rectangle([cx - 15, mouth_y - mouth_h // 2, cx + 15, mouth_y - mouth_h // 2 + 6],
                               fill=(255, 255, 255))

        # Body (shoulders)
        body_top = cy + head_r + 10
        draw.ellipse([cx - 90, body_top, cx + 90, body_top + 160],
                     fill=(70, 130, 200), outline=(50, 100, 170), width=2)

        frames[state] = img

    return frames


def analyze_audio_amplitude(audio_path, fps=30):
    """Analyze audio amplitude to determine mouth state per frame."""
    # Use ffmpeg to extract raw PCM audio
    result = subprocess.run(
        ["ffmpeg", "-i", str(audio_path), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True
    )
    if not result.stdout:
        return []

    raw = result.stdout
    samples_per_frame = 16000 // fps
    num_frames = len(raw) // 2 // samples_per_frame

    states = []
    for i in range(num_frames):
        start = i * samples_per_frame * 2
        end = start + samples_per_frame * 2
        chunk = raw[start:end]

        # Calculate RMS amplitude
        samples = struct.unpack(f"<{len(chunk)//2}h", chunk)
        rms = math.sqrt(sum(s * s for s in samples) / max(len(samples), 1))

        if rms < 500:
            states.append("closed")
        elif rms < 2000:
            states.append("small")
        elif rms < 5000:
            states.append("medium")
        else:
            states.append("wide")

    return states


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

    draw.rectangle([0, 0, width, 6], fill=accent_color)

    y_cursor = 20

    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((150, 150), Image.LANCZOS)
        img.paste(logo, (30, y_cursor), logo)
        y_cursor += 160

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


# ============ PREVIEW FRAME ============
def render_preview_frame(width, height, bg_color, accent_color, title, preview_bg_path=None, logo_path=None):
    if preview_bg_path and os.path.exists(preview_bg_path):
        frame = Image.open(preview_bg_path).convert("RGB")
        frame = frame.resize((width, height), Image.LANCZOS)
    else:
        frame = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(frame)

    draw.rectangle([0, 0, width, 6], fill=accent_color)

    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((150, 150), Image.LANCZOS)
        frame.paste(logo, (30, 20), logo)

    font = load_font(find_font(), 52)
    words = (title or "").split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > width - 100:
            if current:
                lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    line_height = 65
    total_h = len(lines) * line_height
    start_y = (height - total_h) // 2 - 40
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        x = (width - lw) // 2
        for ox in range(-3, 4):
            for oy in range(-3, 4):
                if ox != 0 or oy != 0:
                    draw.text((x + ox, start_y + oy), line, fill=(0, 0, 0), font=font)
        draw.text((x, start_y), line, fill=(255, 255, 255), font=font)
        start_y += line_height

    hint_font = load_font(find_mono_font(), 22)
    hint = "watch to learn"
    hb = draw.textbbox((0, 0), hint, font=hint_font)
    hw = hb[2] - hb[0]
    hx = (width - hw) // 2
    for ox in range(-2, 3):
        for oy in range(-2, 3):
            if ox != 0 or oy != 0:
                draw.text((hx + ox, start_y + 30 + oy), hint, fill=(0, 0, 0), font=hint_font)
    draw.text((hx, start_y + 30), hint, fill=accent_color, font=hint_font)

    return frame


# ============ VIDEO CREATION ============
def create_video(audio_path, caption_chunks, bg_frame, output_path,
                 width, height, fps, captions_enabled,
                 avatar_enabled=False, preview_frame=None, preview_duration=1.5):

    duration = get_audio_duration(audio_path)
    total_frames = int(duration * fps)

    bg_rgb = bg_frame.convert("RGB")

    # Avatar
    avatar_frames_dict = None
    mouth_states = []
    avatar_x, avatar_y = 0, 0
    if avatar_enabled:
        print("  Generating avatar...")
        avatar_frames_dict = generate_avatar_frames()
        target_h = min(420, int(height * 0.33))
        scale = target_h / avatar_frames_dict["closed"].height
        for state in avatar_frames_dict:
            w = int(avatar_frames_dict[state].width * scale)
            h = int(avatar_frames_dict[state].height * scale)
            avatar_frames_dict[state] = avatar_frames_dict[state].resize((w, h), Image.LANCZOS)

        avatar_x = width - avatar_frames_dict["closed"].width - 10
        avatar_y = height - avatar_frames_dict["closed"].height + 50

        print("  Analyzing audio for lip-sync...")
        mouth_states = analyze_audio_amplitude(audio_path, fps=fps)
        while len(mouth_states) < total_frames:
            mouth_states.append("closed")
        mouth_states = mouth_states[:total_frames]

    # Captions
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

    # Preview
    preview_frames_count = int(preview_duration * fps) if preview_frame else 0
    total_with_preview = preview_frames_count + total_frames

    print(f"  Rendering {total_with_preview} frames ({duration + (preview_duration if preview_frame else 0):.1f}s at {fps}fps)...")

    cmd = ["ffmpeg", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{width}x{height}", "-r", str(fps),
           "-i", "pipe:0",
           "-i", str(audio_path)]

    if preview_frame:
        delay_ms = int(preview_duration * 1000)
        cmd += ["-af", f"adelay={delay_ms}|{delay_ms}"]

    cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", str(output_path)]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        # Preview frames
        if preview_frame:
            preview_rgb = preview_frame.convert("RGB")
            for _ in range(preview_frames_count):
                proc.stdin.write(preview_rgb.tobytes())

        # Main frames
        for frame_idx in range(total_frames):
            frame = bg_rgb.copy()

            # Avatar
            if avatar_enabled and avatar_frames_dict:
                mouth = mouth_states[frame_idx]
                avatar_img = avatar_frames_dict[mouth]
                frame.paste(avatar_img, (avatar_x, avatar_y), avatar_img)

            # Caption
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
    parser.add_argument("--avatar", action="store_true", help="Enable lip-synced avatar")
    parser.add_argument("--preview", action="store_true", help="Add preview/intro frame")
    parser.add_argument("--preview-bg", type=str, help="Background image for preview")
    parser.add_argument("--preview-duration", type=float, default=1.5)
    parser.add_argument("--topic", type=int, help="Use built-in topic by index")
    parser.add_argument("--list-topics", action="store_true")
    parser.add_argument("--list-voices", action="store_true")
    parser.add_argument("--lang", type=str, help="Filter voices by language")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list_voices:
        asyncio.run(list_voices(args.lang))
        return

    if args.list_topics:
        print(f"\nBuilt-in topics ({len(SCRIPTS)} total):\n")
        for i, s in enumerate(SCRIPTS):
            print(f"  [{i:2d}] {s['title']}")
            print(f"       {s['hook']}")
        print(f"\n  Usage: generate-video --topic 0 --avatar --preview\n")
        return

    # Topic mode
    if args.topic is not None:
        if args.topic < 0 or args.topic >= len(SCRIPTS):
            print(f"  Topic index must be 0-{len(SCRIPTS)-1}. Use --list-topics to see all.")
            sys.exit(1)
        script = SCRIPTS[args.topic]
        args.text = script["script"]
        args.title = args.title or script["title"]
        args.code = args.code or script["code"]
        print(f"\n  Topic: {script['title']}")
        print(f"  Hook:  {script['hook']}")
        print(f"  Words: {len(script['script'].split())}\n")

    if not args.text:
        parser.print_help()
        sys.exit(1)

    bg_color = hex_to_rgb(args.bg_color)
    accent_color = hex_to_rgb(args.accent_color)

    # Auto-generate output name
    output = args.output
    if not output:
        slug = re.sub(r'[^a-z0-9]+', '_', (args.title or args.text)[:30].lower()).strip('_')
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"{ts}_{slug}.mp4"

    if args.dry_run:
        print(f"\n  DRY RUN:")
        print(f"  Text:     {args.text[:80]}...")
        print(f"  Voice:    {args.voice}")
        print(f"  Title:    {args.title or '(none)'}")
        print(f"  Code:     {(args.code or '(none)')[:50]}")
        print(f"  Logo:     {args.logo or '(none)'}")
        print(f"  Audio:    {args.audio or '(TTS generated)'}")
        print(f"  Size:     {args.width}x{args.height} @ {args.fps}fps")
        print(f"  Avatar:   {'on' if args.avatar else 'off'}")
        print(f"  Preview:  {'on' if args.preview else 'off'}")
        print(f"  Captions: {'off' if args.no_captions else 'on'}")
        print(f"  Output:   {output}\n")
        if args.topic is not None:
            s = SCRIPTS[args.topic]
            print(f"  Hashtags: {s['hashtags']}\n")
        return

    # Step 1: Audio
    temp_audio = False
    audio_path = args.audio
    word_timings = []

    if not audio_path:
        print("Step 1: Generating voice...")
        audio_path = output.replace(".mp4", ".mp3")
        temp_audio = True
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

    # Step 4: Preview frame
    preview_frame_img = None
    if args.preview:
        print("Step 4: Rendering preview frame...")
        preview_frame_img = render_preview_frame(
            args.width, args.height, bg_color, accent_color,
            title=args.title or args.text[:50],
            preview_bg_path=args.preview_bg,
            logo_path=args.logo,
        )
    else:
        print("Step 4: Preview disabled")

    # Step 5: Compose video
    print("Step 5: Creating video...")
    success = create_video(
        audio_path, caption_chunks, bg_frame, output,
        args.width, args.height, args.fps,
        captions_enabled=not args.no_captions,
        avatar_enabled=args.avatar,
        preview_frame=preview_frame_img,
        preview_duration=args.preview_duration,
    )

    # Clean up temp audio
    if temp_audio and Path(audio_path).exists():
        Path(audio_path).unlink()

    if success:
        size_bytes = Path(output).stat().st_size
        if size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.0f} KB"
        else:
            size_str = f"{size_bytes / 1024 / 1024:.1f} MB"
        print(f"\n  Video: {output} ({size_str})")
        if args.topic is not None:
            s = SCRIPTS[args.topic]
            print(f"\n  Caption: {s['hook']}")
            print(f"  Hashtags: {s['hashtags']}")
        print()
    else:
        print("\n  Failed. Check FFmpeg errors above.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
