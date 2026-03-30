import { useState } from 'react';

import * as MonitorSdk from 'error-monitor-sdk';
import * as ReactMonitor from 'error-monitor-sdk/integrations/react';

const { MonitorErrorBoundary } = ReactMonitor;

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

export default function App() {
  return (
    <div style={{ fontFamily: 'system-ui', padding: '1rem', maxWidth: '32rem' }}>
      <h1 style={{ fontSize: '1.25rem' }}>Error Monitor — React + Vite</h1>
      <p style={{ color: '#555', fontSize: '0.9rem' }}>
        Убедитесь, что коллектор запущен, CORS разрешён для этого origin, в <code>.env</code> заданы{' '}
        <code>VITE_*</code>.
      </p>
      <ul style={{ lineHeight: 1.8 }}>
        <li>
          <MonitorErrorBoundary
            fallback={(err) => (
              <span style={{ color: '#b91c1c' }}>Поймано в UI: {err.message} (событие ушло в коллектор)</span>
            )}
          >
            <Bomb />
          </MonitorErrorBoundary>
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
    </div>
  );
}
