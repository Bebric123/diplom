<script setup>
import * as MonitorSdk from 'error-monitor-sdk';

function boom() {
  throw new Error('Vue 3 demo: ошибка через app.config.errorHandler');
}

function track() {
  MonitorSdk.trackEvent('vue_demo_manual', { source: 'vite-demo' }, window.location.href);
}

function globalErr() {
  setTimeout(() => {
    throw new Error('Vue demo: глобальная ошибка (browser.js)');
  }, 0);
}
</script>

<template>
  <div style="font-family: system-ui; padding: 1rem; max-width: 32rem">
    <h1 style="font-size: 1.25rem">Error Monitor — Vue 3 + Vite</h1>
    <p style="color: #555; font-size: 0.9rem">
      CORS на коллекторе, <code>.env</code> с префиксом <code>VITE_</code>.
    </p>
    <ul style="line-height: 2">
      <li><button type="button" @click="boom">Ошибка рендера → errorHandler → /track</button></li>
      <li><button type="button" @click="track">Отправить track_event</button></li>
      <li><button type="button" @click="globalErr">Глобальная ошибка (setTimeout)</button></li>
    </ul>
  </div>
</template>
