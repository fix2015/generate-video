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
    'Generate TikTok-style videos with voice, captions, and overlays from text.\n\n' +
    'Free TTS (edge-tts), Pillow rendering, FFmpeg compositing.\n' +
    'No API key needed.'
  )
  .addHelpText('after', `
${chalk.bold('Examples:')}

  ${chalk.dim('# Generate a video from text')}
  generate-video "JavaScript closures explained in 30 seconds"

  ${chalk.dim('# With a title overlay')}
  generate-video "Your text here" --title "Closures 101"

  ${chalk.dim('# With code overlay')}
  generate-video "Your text" --code "const fn = () => { return 42; }"

  ${chalk.dim('# Custom voice and output')}
  generate-video "Bonjour" --voice fr-FR-HenriNeural --output video.mp4

  ${chalk.dim('# With custom logo')}
  generate-video "Your text" --logo ./my-logo.png

  ${chalk.dim('# Use existing audio instead of TTS')}
  generate-video "Caption text" --audio ./voiceover.mp3

  ${chalk.dim('# Adjust speech speed')}
  generate-video "Fast narration" --rate "+30%"

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
    if (opts.dryRun) args.push('--dry-run');

    runPython(args);
  });

program.parse(process.argv);
