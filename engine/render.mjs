// Render a video project folder to MP4.
// The folder must contain index.html exposing window.seek(t) and window.DURATION.
// Usage: node engine/render.mjs <projectDir> [--fps 30] [--out out/video.mp4] [--from 0 --to 5] [--stills 1]
import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const dir = path.resolve(args[0] || '.');
const opt = (k, d) => { const i = args.indexOf('--' + k); return i > 0 ? args[i + 1] : d; };
const FPS = Number(opt('fps', 30));
const out = path.resolve(dir, opt('out', 'out/video.mp4'));
const stillsEvery = Number(opt('stills', 0)); // >0: write a PNG every N seconds instead of video
mkdirSync(path.dirname(out), { recursive: true });

const executablePath = process.env.CHROME_PATH || await sparticuz.executablePath();
const browser = await chromium.launch({ executablePath, args: sparticuz.args });
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
await page.goto('file://' + path.join(dir, 'index.html'));
await page.evaluate(() => document.fonts.ready);
await page.waitForFunction(() => typeof window.seek === 'function' && window.DURATION > 0);
const DUR = await page.evaluate(() => window.DURATION);
const from = Number(opt('from', 0)), to = Number(opt('to', DUR));

if (stillsEvery > 0) {
  const sdir = path.join(path.dirname(out), 'stills');
  mkdirSync(sdir, { recursive: true });
  for (let t = from; t <= to; t += stillsEvery) {
    await page.evaluate((t) => window.seek(t), t);
    await page.screenshot({ path: path.join(sdir, `t${t.toFixed(1).padStart(5, '0')}.png`) });
  }
  console.log('stills written to', sdir);
  await browser.close();
  process.exit(0);
}

const silent = out.replace(/\.mp4$/, '.silent.mp4');
const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
  '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', silent], { stdio: ['pipe', 'inherit', 'inherit'] });

const cdp = await page.context().newCDPSession(page);
const grab = async () => Buffer.from((await cdp.send('Page.captureScreenshot',
  { format: 'jpeg', quality: 88, optimizeForSpeed: true, fromSurface: true })).data, 'base64');
const total = Math.ceil((to - from) * FPS - 1e-6); // never fewer frames than the audio needs
const t0 = Date.now();
for (let i = 0; i < total; i++) {
  await page.evaluate((t) => window.seek(t), from + i / FPS);
  const buf = await grab();
  if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  if (i % (FPS * 2) === 0) console.log(`frame ${i}/${total} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
}
ff.stdin.end();
await new Promise((r) => ff.on('close', r));
await browser.close();

// Mux audio if present: mix.wav (final) or voice.wav
const audio = ['mix.wav', 'voice.wav'].map((f) => path.join(dir, 'build', f)).find(existsSync);
if (audio) {
  await new Promise((res, rej) => {
    const m = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-i', silent, '-ss', String(from), '-i', audio,
      '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-t', String(to - from), out], { stdio: 'inherit' });
    m.on('close', (c) => (c === 0 ? res() : rej(new Error('mux failed'))));
  });
} else {
  await new Promise((r) => spawn('mv', [silent, out]).on('close', r));
}
console.log('done:', out, `${((Date.now() - t0) / 1000).toFixed(0)}s`);
