import { useState } from 'react';

import * as MonitorSdk from 'error-monitor-sdk';
import * as ReactMonitor from 'error-monitor-sdk/integrations/react';

function MonitorBoundary({ children, fallback }) {
  const B = ReactMonitor.MonitorErrorBoundary;
  if (typeof B !== 'function') {
    return <>{children}</>;
  }
  return <B fallback={fallback}>{children}</B>;
}

function Bomb() {
  const [blow, setBlow] = useState(false);
  if (blow) {
    throw new Error('React demo: ошибка внутри MonitorErrorBoundary');
  }
  return (
    <button type="button" onClick={() => setBlow(true)}>
      Ошибка в Boundary → /track
    </button>
  );
}

function DemoBlock() {
  return (
    <ul style={{ lineHeight: 1.8, marginTop: '0.5rem' }}>
      <li>
        <MonitorBoundary
          fallback={(err) => (
            <span style={{ color: '#b91c1c' }}>Поймано в UI: {err.message} (событие ушло в коллектор)</span>
          )}
        >
          <Bomb />
        </MonitorBoundary>
      </li>
      <li>
        <button
          type="button"
          onClick={() =>
            MonitorSdk.trackEvent('react_demo_manual', { source: 'vite-demo' }, window.location.href)
          }
        >
          Отправить track_event
        </button>
      </li>
      <li>
        <button
          type="button"
          onClick={() => {
            setTimeout(() => {
              throw new Error('React demo: глобальная ошибка (window.onerror / browser.js)');
            }, 0);
          }}
        >
          Глобальная ошибка (через setTimeout)
        </button>
      </li>
    </ul>
  );
}

export default function App({ initError = null, browserIntegWarning = null } = {}) {
  const canUseSdk = !initError;

  return (
    <div style={{ fontFamily: 'system-ui', padding: '1rem', maxWidth: '36rem' }}>
      {initError && (
        <div
          style={{
            marginBottom: '1rem',
            padding: '0.75rem 1rem',
            background: '#fef2f2',
            color: '#991b1b',
            border: '1px solid #fecaca',
            borderRadius: '6px',
            fontSize: '0.9rem',
            whiteSpace: 'pre-wrap',
          }}
        >
          <strong>Коллектор / SDK</strong>
          <br />
          {initError instanceof Error ? initError.message : String(initError)}
        </div>
      )}
      {browserIntegWarning && !initError && (
        <div style={{ marginBottom: '0.75rem', color: '#9a3412', fontSize: '0.85rem' }}>
          enableBrowserIntegration:{' '}
          {browserIntegWarning instanceof Error
            ? browserIntegWarning.message
            : String(browserIntegWarning)}
        </div>
      )}
      <h1 style={{ fontSize: '1.25rem' }}>Error Monitor — React + Vite</h1>
      <p style={{ color: '#555', fontSize: '0.9rem' }}>
        Коллектор <code>{import.meta.env.VITE_MONITOR_URL || 'http://127.0.0.1:8000'}</code> · CORS →{' '}
        <code style={{ fontSize: '0.8rem' }}>CORS_ALLOW_ORIGINS</code> в .env бэкенда. Переменные:{' '}
        <code>VITE_MONITOR_URL</code>, <code>VITE_MONITOR_PROJECT_ID</code>, <code>VITE_MONITOR_API_KEY</code>.
        Откройте DevTools (F12) — вкладка Console, если снова «пусто».
      </p>
      <p style={{ color: '#64748b', fontSize: '0.8rem', marginTop: '0.5rem', maxWidth: '32rem' }}>
        В <strong>режиме разработки</strong> React (даже с Error Boundary) всё равно пишет в консоль полный
        stack выброшенной ошибки — так задумано, это не сбой демо. Событие в коллектор уходит в{' '}
        <code>componentDidCatch</code> SDK. В <code>npm run build</code> + <code>preview</code> сообщений
        в консоли обычно меньше.
      </p>
      <p style={{ color: '#0f172a', fontSize: '0.8rem', marginTop: '0.5rem', maxWidth: '34rem', lineHeight: 1.5 }}>
        <strong>Telegram:</strong> уведомления в чат <em>не</em> шлёт сам браузер. После{' '}
        <code>POST /track</code> коллектор ставит задачу в <strong>очередь Celery</strong> — сообщение
        уйдёт в TG только если запущены <strong>Redis + воркер</strong> (см.{' '}
        <code>project/docker</code> / <code>celery worker</code>) и у проекта в БД задан{' '}
        <code>telegram_chat_id</code> (как при <code>/register</code>). Иначе событие только
        сохраняется в БД.
      </p>
      {canUseSdk ? (
        <DemoBlock />
      ) : (
        <p style={{ color: '#666' }}>После исправления .env кнопки демо станут доступны.</p>
      )}
    </div>
  );
}
