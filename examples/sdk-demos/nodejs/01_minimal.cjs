/**
 * Минимальный сценарий: initMonitor + trackEvent.
 * Запуск из этой папки: node 01_minimal.cjs
 */
const { initMonitor, trackEvent } = require('error-monitor-sdk');

const endpoint = process.env.MONITOR_URL || 'http://127.0.0.1:8000';
const projectId = process.env.MONITOR_PROJECT_ID || '00000000-0000-4000-8000-000000000001';

initMonitor({
  endpoint,
  projectId,
  context: { demo: 'node_minimal' },
  debug: true,
});

trackEvent(
  'sdk_node_manual',
  { note: 'проверка из Node без фреймворка' },
  'https://example.com/node-demo',
);

setTimeout(() => {
  console.log('Готово (очередь успела отправиться).');
  process.exit(0);
}, 2500);
