/**
 * До импорта error-monitor-sdk: Node-специфика в index.js SDK.
 */
if (typeof globalThis.setImmediate === 'undefined') {
  globalThis.setImmediate = (fn, ...args) => {
    return setTimeout(() => fn(...args), 0);
  };
}

if (typeof globalThis.process === 'undefined') {
  globalThis.process = { version: 'browser' };
}
