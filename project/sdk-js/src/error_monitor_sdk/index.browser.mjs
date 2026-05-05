/**
 * Браузерная точка входа (ESM): без require() — для Vite/Webpack "browser".
 * Node-функция sendLogFile (файлы на диске) не поддерживается; используйте index.js (CJS).
 */
import axios from 'axios';

const os = {
  platform: () => 'browser',
  release: () => '',
  hostname: () => 'web',
  arch: () => 'x64',
};

function runAsync(fn) {
  if (typeof setImmediate === 'function') {
    setImmediate(() => fn());
  } else {
    setTimeout(() => fn(), 0);
  }
}

class MonitorClient {
  constructor(options = {}) {
    this.endpoint = options.endpoint?.replace(/\/$/, '') || 'http://localhost:8000';
    this.projectId = options.projectId || 'default-project';
    this.apiKey = (options.apiKey || options.api_key || '').trim() || null;
    this.userIdFunc = options.userIdFunc || (() => 'anonymous');
    this.context = options.context || {};
    this.debug = options.debug || false;

    this.queue = [];
    this.isProcessing = false;

    const run = typeof process !== 'undefined' && process?.version ? String(process.version) : 'browser';
    this.systemInfo = {
      platform: 'backend',
      language: 'javascript',
      runtime: run,
      os_family: os.platform(),
      os_release: os.release(),
      hostname: os.hostname(),
      arch: os.arch(),
    };

    this._log('✅ MonitorClient initialized', { projectId: this.projectId, endpoint: this.endpoint });
  }

  _log(message, data = null) {
    if (this.debug) {
      const timestamp = new Date().toISOString();
      console.log(`[${timestamp}] [MonitorSDK] ${message}`, data ? data : '');
    }
  }

  _authHeaders() {
    if (!this.apiKey) return {};
    return { Authorization: `Bearer ${this.apiKey}` };
  }

  _error(message, error = null) {
    const timestamp = new Date().toISOString();
    console.error(`[${timestamp}] [MonitorSDK] ❌ ${message}`, error ? error : '');
  }

  async _processQueue() {
    if (this.isProcessing || this.queue.length === 0) return;

    this.isProcessing = true;

    while (this.queue.length > 0) {
      const eventData = this.queue.shift();
      try {
        await this._sendSync(eventData);
      } catch (error) {
        this._error('Failed to send event', error);
        if (error.code === 'ECONNREFUSED' || error.code === 'ENOTFOUND') {
          this.queue.unshift(eventData);
          this._log('Event returned to queue (connection error)');
        }
        break;
      }
    }

    this.isProcessing = false;

    if (this.queue.length > 0) {
      runAsync(() => this._processQueue());
    }
  }

  async _sendSync(payload) {
    try {
      // User-Agent в браузере — запрежён; при необходимости сервер смотрит обычный User-Agent
      const response = await axios.post(`${this.endpoint}/track`, payload, {
        headers: {
          'Content-Type': 'application/json',
          'X-Monitor-Client': 'ErrorMonitor-SDK/1.0 (browser)',
          ...this._authHeaders(),
        },
        timeout: 5000,
      });

      if (response.status === 200) {
        this._log('✅ Event sent successfully', { action: payload.action });
      } else {
        this._error('Failed to send event', { status: response.status, data: response.data });
      }

      return response;
    } catch (error) {
      if (error.response) {
        this._error('Server error', {
          status: error.response.status,
          data: error.response.data,
        });
      } else if (error.request) {
        this._error('No response from server', { endpoint: this.endpoint });
      } else {
        this._error('Request error', error.message);
      }
      throw error;
    }
  }

  sendEvent(action, metadata = {}, pageUrl = null, context = {}) {
    try {
      const userId = typeof this.userIdFunc === 'function' ? this.userIdFunc() : 'anonymous';

      const finalContext = {
        platform: 'backend',
        language: 'javascript',
        os_family: this.systemInfo.os_family,
        browser_family: 'node',
        ...this.context,
        ...context,
      };

      const run =
        typeof process !== 'undefined' && process?.version
          ? String(process.version)
          : 'browser';

      const payload = {
        project_id: this.projectId,
        action: action,
        timestamp: new Date().toISOString(),
        context: {
          platform: finalContext.platform || 'backend',
          language: finalContext.language || 'javascript',
          os_family: finalContext.os_family || os.platform(),
          browser_family: finalContext.browser_family || 'node',
        },
        meta: {
          user_id: userId,
          page_url: pageUrl || 'server-side',
          sdk_version: '1.0.0',
          runtime: run,
          ...metadata,
        },
      };

      for (const [key, value] of Object.entries(finalContext)) {
        if (!['platform', 'language', 'os_family', 'browser_family'].includes(key)) {
          payload.meta[`context_${key}`] = value;
        }
      }

      this.queue.push(payload);
      this._log('Event queued', { action, queueLength: this.queue.length });
      runAsync(() => this._processQueue());
    } catch (error) {
      this._error('Error creating event', error);
    }
  }

  captureException(error, metadata = {}, pageUrl = null) {
    const errorMetadata = {
      exception_type: error.name || 'Error',
      error_message: error.message,
      error_stack: error.stack,
      stack_trace: error.stack,
      ...metadata,
    };

    this.sendEvent(
      `exception: ${error.name || 'Error'}`,
      errorMetadata,
      pageUrl
    );
  }

  setContext(context) {
    this.context = { ...this.context, ...context };
    this._log('Context updated', context);
  }

  clearContext() {
    this.context = {};
    this._log('Context cleared');
  }

  sendLogFile(_filepath, _options = {}) {
    console.warn(
      '⚠️ sendLogFile() доступен только в Node.js; используйте `require(\"error-monitor-sdk\")` на сервере.',
    );
    return false;
  }
}

let _client = null;

function initMonitor(options = {}) {
  _client = new MonitorClient(options);
  return _client;
}

function trackEvent(action, metadata = {}, pageUrl = null) {
  if (!_client) {
    throw new Error('❌ Call initMonitor() first');
  }
  _client.sendEvent(action, metadata, pageUrl);
}

function captureException(error, metadata = {}, pageUrl = null) {
  if (!_client) {
    console.warn('⚠️ SDK not initialized, exception not captured');
    return;
  }
  _client.captureException(error, metadata, pageUrl);
}

function setContext(context) {
  if (!_client) {
    throw new Error('❌ Call initMonitor() first');
  }
  _client.setContext(context);
}

function clearContext() {
  if (!_client) {
    throw new Error('❌ Call initMonitor() first');
  }
  _client.clearContext();
}

function getClient() {
  return _client;
}

function sendLogFile(filepath, options = {}) {
  if (!_client) {
    throw new Error('❌ Call initMonitor() first');
  }
  return _client.sendLogFile(filepath, options);
}

export {
  initMonitor,
  trackEvent,
  captureException,
  setContext,
  clearContext,
  getClient,
  sendLogFile,
};
