/**
 * Fastify + SDK. Порт 8021.
 * Запуск: node 03_fastify_demo.cjs
 */
const Fastify = require('fastify');
const { initMonitor } = require('error-monitor-sdk');
const { enableFastifyIntegration } = require('error-monitor-sdk/integrations/fastify');

const endpoint = process.env.MONITOR_URL || 'http://127.0.0.1:8000';
const projectId = process.env.MONITOR_PROJECT_ID || '00000000-0000-4000-8000-000000000001';

initMonitor({
  endpoint,
  projectId,
  context: { demo: 'fastify' },
  debug: true,
});

const fastify = Fastify({ logger: false });

enableFastifyIntegration(fastify, {
  userIdFunc: (req) => req.headers['x-user-id'] || req.ip || 'anonymous',
  captureErrors: true,
  captureRequests: true,
});

fastify.get('/', async () => ({ ok: true }));

fastify.get('/boom', async () => {
  throw new Error('тестовая ошибка Fastify для SDK');
});

fastify.listen({ port: 8021, host: '127.0.0.1' }, (err) => {
  if (err) throw err;
  console.log('Fastify demo http://127.0.0.1:8021 (GET /boom)');
});
