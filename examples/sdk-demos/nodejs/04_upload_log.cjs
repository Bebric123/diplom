/**
 * Отправка лога через SDK (как в Python send_log_file).
 * Запуск: node 04_upload_log.cjs
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const { initMonitor, sendLogFile } = require('error-monitor-sdk');

const endpoint = process.env.MONITOR_URL || 'http://127.0.0.1:8000';
const projectId = process.env.MONITOR_PROJECT_ID || 'edb9ac0b-c0a5-45ee-829d-91ed250d4cd3';
const apiKey = "pLD-lQWqPiPQfIvDUNLNE_2ohTCgfIjzDPUSZHPLrLY";
initMonitor({
  endpoint,
  projectId,
  apiKey,
  context: { environment: 'demo' },
  debug: true,
});

const filePath = path.join(os.tmpdir(), `sdk-log-${Date.now()}.log`);
fs.writeFileSync(filePath, 'info: start\nERROR node SDK sendLogFile demo\n', 'utf8');

const ok = sendLogFile(filePath, {
  lines: 10,
  serviceName: 'nodejs-demo',
  environment: 'demo',
});

console.log('sendLogFile queued:', ok);

setTimeout(() => {
  console.log('Готово (запрос ушёл в фоне).');
  process.exit(0);
}, 3000);
