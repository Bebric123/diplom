// Браузер: только ESM (Vite/rollup) — в бандле не должно оставаться require()
// Точка входа — пакет `error-monitor-sdk`, не относительный `../index.browser.mjs`, иначе
// Vite (optimizeDeps) может дать два экземпляра модуля и getClient() после initMonitor() = null.
import { getClient } from 'error-monitor-sdk';

/**
 * Подключает мониторинг к браузеру
 * @param {Object} options - Опции
 * @param {Function} options.userIdFunc - Функция для получения userId
 * @param {boolean} options.captureGlobalErrors - Перехватывать глобальные ошибки
 * @param {boolean} options.captureUnhandledRejections - Перехватывать unhandled rejections
 */
function enableBrowserIntegration(options = {}) {
  const client = getClient();

  if (!client) {
    console.warn('⚠️ ErrorMonitor SDK not initialized. Call initMonitor() first.');
    return;
  }

  const {
    userIdFunc = () => {
      let userId = localStorage.getItem('monitor_user_id');
      if (!userId) {
        userId = 'browser_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('monitor_user_id', userId);
      }
      return userId;
    },
    captureGlobalErrors = true,
    captureUnhandledRejections = true,
  } = options;

  const browserInfo = {
    userAgent: navigator.userAgent,
    language: navigator.language,
    platform: navigator.platform,
    vendor: navigator.vendor,
    cookieEnabled: navigator.cookieEnabled,
    screenSize: `${window.screen.width}x${window.screen.height}`,
    viewportSize: `${window.innerWidth}x${window.innerHeight}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    referrer: document.referrer || 'direct',
    title: document.title,
  };

  client.setContext({
    platform: 'frontend',
    language: 'javascript',
    browser_family: navigator.userAgent.includes('Chrome')
      ? 'chrome'
      : navigator.userAgent.includes('Firefox')
        ? 'firefox'
        : navigator.userAgent.includes('Safari')
          ? 'safari'
          : 'unknown',
    os_family: navigator.userAgent.includes('Windows')
      ? 'Windows'
      : navigator.userAgent.includes('Mac')
        ? 'macOS'
        : navigator.userAgent.includes('Linux')
          ? 'Linux'
          : 'unknown',
    ...browserInfo,
  });

  if (captureGlobalErrors) {
    window.addEventListener('error', (event) => {
      client.captureException(
        event.error || new Error(event.message),
        {
          type: 'global_error',
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno,
          url: window.location.href,
          user_id: userIdFunc(),
        },
        window.location.href,
      );
    });
  }

  if (captureUnhandledRejections) {
    window.addEventListener('unhandledrejection', (event) => {
      const error = event.reason instanceof Error ? event.reason : new Error(String(event.reason));
      client.captureException(
        error,
        {
          type: 'unhandled_rejection',
          url: window.location.href,
          user_id: userIdFunc(),
        },
        window.location.href,
      );
    });
  }

  if (window.performance) {
    window.addEventListener('load', () => {
      const perfData = performance.timing;
      const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;

      client.sendEvent(
        'page_load',
        {
          load_time_ms: pageLoadTime,
          dom_ready_ms: perfData.domComplete - perfData.domLoading,
          url: window.location.href,
          user_id: userIdFunc(),
        },
        window.location.href,
      );
    });
  }

  console.log('✅ Browser integration enabled');
}

export { enableBrowserIntegration };
