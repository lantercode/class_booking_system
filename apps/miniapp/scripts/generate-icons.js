const fs = require('fs');
const path = require('path');

const tabsDir = path.join(__dirname, '../src/static/tabs');

const icons = {
  'home': createSimpleIcon('#999999'),
  'home-active': createSimpleIcon('#1989fa'),
  'booking': createSimpleIcon('#999999'),
  'booking-active': createSimpleIcon('#1989fa'),
  'schedule': createSimpleIcon('#999999'),
  'schedule-active': createSimpleIcon('#1989fa'),
  'profile': createSimpleIcon('#999999'),
  'profile-active': createSimpleIcon('#1989fa'),
};

function createSimpleIcon(color) {
  const size = 64;
  const png = Buffer.alloc(8 + 25 + 12 + size * size * 4 + 12 + 16);
  
  let offset = 0;
  
  const signature = Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);
  signature.copy(png, offset);
  offset += 8;
  
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;
  
  const ihdrChunk = createChunk('IHDR', ihdr);
  ihdrChunk.copy(png, offset);
  offset += ihdrChunk.length;
  
  const rawData = Buffer.alloc(size * size * 4);
  const [r, g, b] = hexToRgb(color);
  
  for (let y = 0; y < size; y++) {
    rawData[y * size * 4] = 0;
    for (let x = 0; x < size; x++) {
      const idx = y * size * 4 + x * 4 + 1;
      rawData[idx] = r;
      rawData[idx + 1] = g;
      rawData[idx + 2] = b;
      rawData[idx + 3] = 255;
    }
  }
  
  const zlib = require('zlib');
  const compressed = zlib.deflateSync(rawData);
  
  const idatChunk = createChunk('IDAT', compressed);
  const fullPng = Buffer.concat([
    signature,
    ihdrChunk,
    idatChunk,
    createChunk('IEND', Buffer.alloc(0))
  ]);
  
  return fullPng;
}

function createChunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length, 0);
  
  const typeBuffer = Buffer.from(type);
  const crcData = Buffer.concat([typeBuffer, data]);
  const crc = crc32(crcData);
  
  const crcBuffer = Buffer.alloc(4);
  crcBuffer.writeUInt32BE(crc >>> 0, 0);
  
  return Buffer.concat([length, typeBuffer, data, crcBuffer]);
}

function crc32(data) {
  let crc = 0xFFFFFFFF;
  const table = [];
  
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let j = 0; j < 8; j++) {
      c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    }
    table[i] = c;
  }
  
  for (let i = 0; i < data.length; i++) {
    crc = table[(crc ^ data[i]) & 0xFF] ^ (crc >>> 8);
  }
  
  return crc ^ 0xFFFFFFFF;
}

function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? [
    parseInt(result[1], 16),
    parseInt(result[2], 16),
    parseInt(result[3], 16)
  ] : [153, 153, 153];
}

if (!fs.existsSync(tabsDir)) {
  fs.mkdirSync(tabsDir, { recursive: true });
}

Object.entries(icons).forEach(([name, png]) => {
  fs.writeFileSync(path.join(tabsDir, `${name}.png`), png);
  console.log(`Created ${name}.png`);
});

console.log('All icons generated successfully!');