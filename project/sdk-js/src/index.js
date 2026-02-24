class ErrorMonitor {
  static init(config) {
    this.endpoint = config.endpoint;
    this.apiKey = config.apiKey;

    if (config.autoCapture !== false) {
      this.enableAutoCapture();
    }
  }

  static enableAutoCapture() {
    window.addEventListener('error', (e) => {
      this.sendEvent('js_error', {
        message: e.message,
        filename: e.filename,
        lineno: e.lineno,
        colno: e.colno,
        stack: e.error?.stack || ''
      });
    });

    window.addEventListener('unhandledrejection', (e) => {
      this.sendEvent('unhandled_promise', {
        reason: String(e.reason),
        stack: e.reason?.stack || ''
      });
    });
  }

  static track(action, metadata = {}) {
    this.sendEvent(action, metadata);
  }

  static sendEvent(action, metadata) {
    if (!this.endpoint) {
      console.warn('[ErrorMonitor] Not initialized');
      return;
    }

    const payload = {
      user_id: 'anonymous',
      action: action,
      page_url: window.location.href,
      timestamp: new Date().toISOString(),
      metadata: metadata
    };

    if (navigator.sendBeacon) {
      navigator.sendBeacon(this.endpoint, JSON.stringify(payload));
    } else {
      fetch(this.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true
      }).catch(() => {});
    }
  }
}

if (typeof window !== 'undefined') {
  window.ErrorMonitor = ErrorMonitor;
}

export default ErrorMonitor;