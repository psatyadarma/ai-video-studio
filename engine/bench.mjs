import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';
import path from 'node:path';
const dir = path.resolve(process.argv[2]); const css = process.argv[3] || '';
const b = await chromium.launch({ executablePath: await sparticuz.executablePath(), args: sparticuz.args });
const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
await p.goto('file://' + dir + '/index.html');
await p.waitForFunction(() => window.DURATION > 0);
if (css) await p.addStyleTag({ content: css });
let a=Date.now(); for (let i = 0; i < 6; i++) await p.evaluate((t) => seek(t), 4 + i / 30); const seekMs=(Date.now()-a)/6;
const t0 = Date.now();
for (let i = 0; i < 6; i++) { await p.evaluate((t) => seek(t), 4 + i / 30); await p.screenshot({ type: 'jpeg', quality: 92 }); }
console.log(JSON.stringify({css: css.slice(0,40), seekMs, frameMs: (Date.now() - t0) / 6}));
await b.close();
