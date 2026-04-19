/**
 * Express + middleware SDK. Порт 8020 (коллектор остаётся на 8000).
 * Запуск: node 02_express_demo.cjs
 * Проверка: curl http://127.0.0.1:8020/boom
 */
const express = require('express');
const { initMonitor } = require('error-monitor-sdk');
const { enableExpressIntegration } = require('error-monitor-sdk/integrations/express');

const endpoint = process.env.MONITOR_URL || 'http://127.0.0.1:8000';
const projectId = process.env.MONITOR_PROJECT_ID || 'edb9ac0b-c0a5-45ee-829d-91ed250d4cd3';
const apiKey = "pLD-lQWqPiPQfIvDUNLNE_2ohTCgfIjzDPUSZHPLrLY";

initMonitor({
  endpoint,
  projectId,
  apiKey,
  context: { demo: 'express' },
  debug: true,
});

const app = express();
enableExpressIntegration(app, {
  userIdFunc: (req) => req.headers['x-user-id'] || req.ip || 'anonymous',
  captureErrors: true,
  captureRequests: true,
});

app.get('/', (_req, res) => res.json({ ok: true }));

app.get('/boom', (_req, _res, next) => {
  next(new Error('тестовая ошибка Express для SDK'));
});

app.listen(8020, () => {
  console.log('Express demo http://127.0.0.1:8020 (GET /boom для ошибки)');
});
