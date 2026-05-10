import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const appPath = resolve(__dirname, '../src/views/ChatPage.vue');
const source = readFileSync(appPath, 'utf8');

const humanApprovalCase = source.match(/case ['"]HUMAN_APPROVAL['"]:[\s\S]*?break\b/);
if (!humanApprovalCase) {
  throw new Error('HUMAN_APPROVAL case not found');
}

if (/reader\s*=\s*null/.test(humanApprovalCase[0])) {
  throw new Error('HUMAN_APPROVAL handler must not clear the active stream reader while the read loop is still running');
}

const hasLocalReaderReadLoop =
  /const\s+activeReader\s*=\s*response\.body\.getReader\(\)[\s\S]*?await\s+activeReader\.read\(\)/.test(source);
if (!hasLocalReaderReadLoop) {
  throw new Error('SSE read loop should read from a local activeReader instead of the mutable global reader');
}

console.log('approval stream reader regression checks passed');
