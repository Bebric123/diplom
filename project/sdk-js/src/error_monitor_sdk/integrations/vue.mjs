/**
 * Vue-интеграция (ESM, без require) — для Vite/браузера.
 */
import { getClient } from 'error-monitor-sdk';

/**
 * @param {import('vue').App} app
 * @param {{ onError?: (err: unknown, instance: unknown, info: string) => void }} [options]
 */
function installVue3Monitor(app, options = {}) {
  const prev = app.config.errorHandler;
  app.config.errorHandler = (err, instance, info) => {
    const client = getClient();
    if (client && typeof window !== 'undefined') {
      const error = err instanceof Error ? err : new Error(String(err));
      let componentName;
      try {
        componentName =
          (instance && instance.$options && instance.$options.name) ||
          (instance && instance.$ && instance.$.type && instance.$.type.name);
      } catch (_) {
        componentName = undefined;
      }
      client.captureException(
        error,
        {
          source: 'vue3_error_handler',
          info: String(info),
          component: componentName,
        },
        window.location.href,
      );
    }
    if (typeof options.onError === 'function') {
      options.onError(err, instance, info);
    }
    if (typeof prev === 'function') {
      prev(err, instance, info);
    }
  };
}

/**
 * @param {typeof import('vue').default} Vue
 * @param {{ onError?: (err: Error, vm: unknown, info: string) => void }} [options]
 */
function installVue2Monitor(Vue, options = {}) {
  const prev = Vue.config.errorHandler;
  Vue.config.errorHandler = (err, vm, info) => {
    const client = getClient();
    if (client && typeof window !== 'undefined') {
      const error = err instanceof Error ? err : new Error(String(err));
      client.captureException(
        error,
        {
          source: 'vue2_error_handler',
          info: String(info),
          component: vm && vm.$options && vm.$options.name,
        },
        window.location.href,
      );
    }
    if (typeof options.onError === 'function') {
      options.onError(err, vm, info);
    }
    if (typeof prev === 'function') {
      prev(err, vm, info);
    }
  };
}

export { installVue3Monitor, installVue2Monitor };
