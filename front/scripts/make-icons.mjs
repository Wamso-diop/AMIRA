// Génère les icônes d'extension (16/32/48/128) depuis le symbole et les variantes du logo
// complet (fond transparent, version claire pour le thème sombre). Source : images de la racine.
import sharp from 'sharp';
import { mkdirSync } from 'node:fs';

const SYMBOL = 'amira.png';
const FULL = 'amora_nom.png';
const AUBERGINE = [0x48, 0x1c, 0x4b];

/** Rogne selon la transparence existante ; option : éclaircir l'aubergine (thème sombre). */
async function toTransparent(file, { lighten = false } = {}) {
  const { data, info } = await sharp(file).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  let minX = info.width, minY = info.height, maxX = 0, maxY = 0;
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] < 16) continue;
    if (lighten && Math.abs(data[i] - AUBERGINE[0]) < 40 && Math.abs(data[i + 1] - AUBERGINE[1]) < 40 && Math.abs(data[i + 2] - AUBERGINE[2]) < 40) {
      data[i] = 0xf8; data[i + 1] = 0xee; data[i + 2] = 0xf7;
    }
    const p = i / 4, x = p % info.width, y = Math.floor(p / info.width);
    if (x < minX) minX = x; if (x > maxX) maxX = x; if (y < minY) minY = y; if (y > maxY) maxY = y;
  }
  const raw = await sharp(data, { raw: { width: info.width, height: info.height, channels: 4 } }).png().toBuffer();
  return sharp(raw).extract({ left: minX, top: minY, width: maxX - minX + 1, height: maxY - minY + 1 });
}

mkdirSync('public/icons', { recursive: true });
mkdirSync('src/assets', { recursive: true });

const symbol = await (await toTransparent(SYMBOL)).png().toBuffer();
for (const size of [16, 32, 48, 128]) {
  const pad = size <= 16 ? 0 : Math.round(size * 0.06);
  await sharp(symbol)
    .resize(size - pad * 2, size - pad * 2, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .extend({ top: pad, bottom: pad, left: pad, right: pad, background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .png().toFile(`public/icons/icon-${size}.png`);
}
await sharp(symbol).resize(256, 256, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } }).png().toFile('src/assets/amira-symbole.png');
await (await toTransparent(FULL)).resize({ height: 160 }).png().toFile('src/assets/amira-logo.png');
await (await toTransparent(FULL, { lighten: true })).resize({ height: 160 }).png().toFile('src/assets/amira-logo-clair.png');
console.log('Icônes et logos générés.');
