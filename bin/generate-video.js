#!/usr/bin/env node

'use strict';

const { program } = require('commander');
const { execSync, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const chalk = require('chalk');

const pkg = require('../package.json');
const SCRIPTS_DIR = path.join(__dirname, '..', 'scripts');
const PYTHON_SCRIPT = path.join(SCRIPTS_DIR, 'generate_video.py');

function checkPython() {
  try {
    execSync('python3 --version', { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

function checkPythonDeps() {
  try {
    execSync('python3 -c "import edge_tts; from PIL import Image, ImageDraw, ImageFont"', {
      stdio: 'pipe',
      timeout: 10000,
    });
    return true;
  } catch {
    return false;
  }
}

function checkFFmpeg() {
  try {
    execSync('ffmpeg -version', { stdio: 'pipe' });
    execSync('ffprobe -version', { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

function installPythonDeps() {
  console.log(chalk.yellow('Installing Python dependencies...'));
  try {
    execSync('pip3 install edge-tts Pillow', { stdio: 'inherit' });
    return true;
  } catch {
    console.error(chalk.red('Failed. Try manually: pip3 install edge-tts Pillow'));
    return false;
  }
}

function ensureDeps() {
  if (!checkPython()) {
    console.error(chalk.red('Python 3 is required.'));
    console.error('  Install: https://www.python.org/downloads/');
    process.exit(1);
  }
  if (!checkFFmpeg()) {
    console.error(chalk.red('FFmpeg is required.'));
    console.error('  macOS:   brew install ffmpeg');
    console.error('  Ubuntu:  sudo apt install ffmpeg');
    console.error('  Windows: choco install ffmpeg');
    process.exit(1);
  }
  if (!checkPythonDeps()) {
    if (!installPythonDeps()) process.exit(1);
  }
}

function runPython(args) {
  const child = spawn('python3', [PYTHON_SCRIPT, ...args], {
    stdio: 'inherit',
    env: { ...process.env },
  });
  child.on('close', (code) => {
    process.exit(code || 0);
  });
}

program
  .name('generate-video')
  .version(pkg.version)
  .description(
    'Generate TikTok-style videos with voice, captions, avatar, and overlays.\n\n' +
    'Free TTS (edge-tts), Pillow rendering, FFmpeg compositing.\n' +
    'No API key needed.'
  )
  .addHelpText('after', `
${chalk.bold('Examples:')}

  ${chalk.dim('# Generate a video from text')}
  generate-video "JavaScript closures explained in 30 seconds"

  ${chalk.dim('# With title, code overlay, and avatar')}
  generate-video "Your text" --title "Closures 101" --code "const x = 42;" --avatar

  ${chalk.dim('# With preview intro frame')}
  generate-video "Your text" --title "My Video" --preview

  ${chalk.dim('# With preview background image')}
  generate-video "Your text" --preview --preview-bg ./bg.png

  ${chalk.dim('# Use a built-in topic from the script bank')}
  generate-video --topic 0
  generate-video --topic 5 --avatar --preview

  ${chalk.dim('# List all built-in topics')}
  generate-video --topics

  ${chalk.dim('# Custom voice, logo, colors')}
  generate-video "Bonjour" --voice fr-FR-HenriNeural --logo ./logo.png

  ${chalk.dim('# Use existing audio')}
  generate-video "Caption text" --audio ./voiceover.mp3

  ${chalk.dim('# Preview without generating')}
  generate-video "Your text" --dry-run

  ${chalk.dim('# List available voices')}
  generate-video --voices --lang en
`);

// ---- SETUP ----
program
  .command('setup')
  .description('Check environment and install dependencies (Python, edge-tts, Pillow, FFmpeg)')
  .action(() => {
    console.log(chalk.bold('\ngenerate-video setup\n'));

    if (!checkPython()) {
      console.error(chalk.red('  Python 3 not found.'));
      process.exit(1);
    }
    console.log(chalk.green('  Python 3 found'));

    if (!checkFFmpeg()) {
      console.error(chalk.red('  FFmpeg not found.'));
      console.error('  macOS: brew install ffmpeg');
      console.error('  Ubuntu: sudo apt install ffmpeg');
      process.exit(1);
    }
    console.log(chalk.green('  FFmpeg found'));

    if (!checkPythonDeps()) {
      if (!installPythonDeps()) process.exit(1);
    } else {
      console.log(chalk.green('  edge-tts + Pillow installed'));
    }

    console.log(chalk.bold('\n  Ready! Try: generate-video "Hello world"\n'));
  });

// ---- DEFAULT: generate video ----
program
  .argument('[text]', 'Text for voiceover and captions')
  .option('-v, --voice <name>', 'TTS voice (default: en-US-GuyNeural)', 'en-US-GuyNeural')
  .option('-o, --output <file>', 'Output video file path (default: auto-generated)')
  .option('-t, --title <text>', 'Title text overlay on the video')
  .option('-c, --code <text>', 'Code overlay text (shown in a code box)')
  .option('--logo <path>', 'Path to logo image (PNG, top-left corner)')
  .option('--audio <path>', 'Use existing audio file instead of generating TTS')
  .option('-r, --rate <rate>', 'Speech rate for TTS (e.g. "+20%", "-10%")')
  .option('-p, --pitch <pitch>', 'Voice pitch (e.g. "+5Hz", "-2Hz")')
  .option('--width <px>', 'Video width in pixels', '720')
  .option('--height <px>', 'Video height in pixels', '1280')
  .option('--fps <n>', 'Frames per second', '30')
  .option('--bg-color <hex>', 'Background color hex (default: 0f172a)', '0f172a')
  .option('--accent-color <hex>', 'Accent color hex (default: 7c3aed)', '7c3aed')
  .option('--no-captions', 'Disable animated captions')
  .option('--avatar', 'Enable lip-synced animated avatar')
  .option('--preview', 'Add 1.5s branded preview/intro frame')
  .option('--preview-bg <path>', 'Background image for preview frame (PNG)')
  .option('--preview-duration <sec>', 'Preview frame duration in seconds', '1.5')
  .option('--topic <index>', 'Use built-in topic by index (see --topics)')
  .option('--topics', 'List all built-in topics')
  .option('--voices', 'List all available TTS voices')
  .option('-l, --lang <code>', 'Filter voices by language (e.g. en, fr)')
  .option('--dry-run', 'Preview settings without generating video')
  .action((text, opts) => {
    // List voices mode
    if (opts.voices) {
      ensureDeps();
      const args = ['--list-voices'];
      if (opts.lang) args.push('--lang', opts.lang);
      runPython(args);
      return;
    }

    // List topics mode
    if (opts.topics) {
      ensureDeps();
      runPython(['--list-topics']);
      return;
    }

    // Topic mode (no text needed)
    if (opts.topic !== undefined) {
      ensureDeps();
      const args = ['--topic', opts.topic];
      if (opts.output) args.push('--output', path.resolve(opts.output));
      if (opts.voice !== 'en-US-GuyNeural') args.push('--voice', opts.voice);
      if (opts.logo) args.push('--logo', path.resolve(opts.logo));
      if (opts.rate) args.push('--rate', opts.rate);
      if (opts.pitch) args.push('--pitch', opts.pitch);
      if (opts.width !== '720') args.push('--width', opts.width);
      if (opts.height !== '1280') args.push('--height', opts.height);
      if (opts.fps !== '30') args.push('--fps', opts.fps);
      if (opts.bgColor !== '0f172a') args.push('--bg-color', opts.bgColor);
      if (opts.accentColor !== '7c3aed') args.push('--accent-color', opts.accentColor);
      if (opts.captions === false) args.push('--no-captions');
      if (opts.avatar) args.push('--avatar');
      if (opts.preview) args.push('--preview');
      if (opts.previewBg) args.push('--preview-bg', path.resolve(opts.previewBg));
      if (opts.previewDuration !== '1.5') args.push('--preview-duration', opts.previewDuration);
      if (opts.dryRun) args.push('--dry-run');
      runPython(args);
      return;
    }

    if (!text) {
      program.help();
      return;
    }

    ensureDeps();

    const args = ['--text', text, '--voice', opts.voice];
    if (opts.output) args.push('--output', path.resolve(opts.output));
    if (opts.title) args.push('--title', opts.title);
    if (opts.code) args.push('--code', opts.code);
    if (opts.logo) args.push('--logo', path.resolve(opts.logo));
    if (opts.audio) args.push('--audio', path.resolve(opts.audio));
    if (opts.rate) args.push('--rate', opts.rate);
    if (opts.pitch) args.push('--pitch', opts.pitch);
    if (opts.width !== '720') args.push('--width', opts.width);
    if (opts.height !== '1280') args.push('--height', opts.height);
    if (opts.fps !== '30') args.push('--fps', opts.fps);
    if (opts.bgColor !== '0f172a') args.push('--bg-color', opts.bgColor);
    if (opts.accentColor !== '7c3aed') args.push('--accent-color', opts.accentColor);
    if (opts.captions === false) args.push('--no-captions');
    if (opts.avatar) args.push('--avatar');
    if (opts.preview) args.push('--preview');
    if (opts.previewBg) args.push('--preview-bg', path.resolve(opts.previewBg));
    if (opts.previewDuration !== '1.5') args.push('--preview-duration', opts.previewDuration);
    if (opts.dryRun) args.push('--dry-run');

    runPython(args);
  });

program.parse(process.argv);
