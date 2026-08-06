const fs = require('fs');
const path = require('path');

const iconsDir = path.join(__dirname, '../src/static/tabs');

if (!fs.existsSync(iconsDir)) {
  fs.mkdirSync(iconsDir, { recursive: true });
}

const createPNG = (width, height, r, g, b, a = 255) => {
  const signature = Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);
  
  const createChunk = (type, data) => {
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length, 0);
    const typeBuffer = Buffer.from(type);
    const crcData = Buffer.concat([typeBuffer, data]);
    const crc = crc32(crcData);
    const crcBuffer = Buffer.alloc(4);
    crcBuffer.writeUInt32BE(crc >>> 0, 0);
    return Buffer.concat([length, typeBuffer, data, crcBuffer]);
  };
  
  const crc32 = (buf) => {
    let crc = -1;
    for (let i = 0; i < buf.length; i++) {
      crc = (crc >>> 8) ^ crcTable[(crc ^ buf[i]) & 0xff];
    }
    return crc ^ -1;
  };
  
  const crcTable = [];
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    crcTable[n] = c;
  }
  
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;
  
  const rawData = [];
  for (let y = 0; y < height; y++) {
    rawData.push(0);
    for (let x = 0; x < width; x++) {
      rawData.push(r, g, b, a);
    }
  }
  
  const zlib = require('zlib');
  const compressed = zlib.deflateSync(Buffer.from(rawData));
  
  const ihdrChunk = createChunk('IHDR', ihdr);
  const idatChunk = createChunk('IDAT', compressed);
  const iendChunk = createChunk('IEND', Buffer.alloc(0));
  
  return Buffer.concat([signature, ihdrChunk, idatChunk, iendChunk]);
};

const icons = [
  { name: 'home.png', color: [153, 153, 153] },
  { name: 'home-active.png', color: [102, 126, 234] },
  { name: 'course.png', color: [153, 153, 153] },
  { name: 'course-active.png', color: [102, 126, 234] },
  { name: 'booking.png', color: [153, 153, 153] },
  { name: 'booking-active.png', color: [102, 126, 234] },
  { name: 'profile.png', color: [153, 153, 153] },
  { name: 'profile-active.png', color: [102, 126, 234] },
];

icons.forEach(icon => {
  const png = createPNG(48, 48, icon.color[0], icon.color[1], icon.color[2]);
  fs.writeFileSync(path.join(iconsDir, icon.name), png);
  console.log(`Created ${icon.name}`);
});

console.log('All icons created successfully!');