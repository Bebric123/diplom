/**
 * Vue: глобальный errorHandler (Vue 3) или Vue.config.errorHandler (Vue 2).
 * Ошибки из setup/render, не пойманные в компонентах, уходят сюда.
 * Peer: `vue` (2 или 3 — разные функции установки).
 */
const { getClient } = require('../index');

/**
 * Vue 3: после createApp(App).use(router) вызовите installVue3Monitor(app).
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
 * Vue 2: один раз при старте — installVue2Monitor(Vue).
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

module.exports = {
  installVue3Monitor,
  installVue2Monitor,
};
