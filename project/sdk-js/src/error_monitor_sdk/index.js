// error-monitor-sdk/index.js
const axios = require('axios');
const os = require('os');
const { sendLogFile: uploadLogFile } = require('./logs');

class MonitorClient {
    constructor(options = {}) {
        this.endpoint = options.endpoint?.replace(/\/$/, '') || 'http://localhost:8000';
        this.projectId = options.projectId || 'default-project';
        this.apiKey = (options.apiKey || options.api_key || '').trim() || null;
        this.userIdFunc = options.userIdFunc || (() => 'anonymous');
        this.context = options.context || {};
        this.debug = options.debug || false;
        
        // Очередь для асинхронной отправки
        this.queue = [];
        this.isProcessing = false;
        
        // Информация о системе
        this.systemInfo = {
            platform: 'backend',
            language: 'javascript',
            runtime: process.version,
            os_family: os.platform(),
            os_release: os.release(),
            hostname: os.hostname(),
            arch: os.arch()
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
                // Можно вернуть в очередь при ошибке сети
                if (error.code === 'ECONNREFUSED' || error.code === 'ENOTFOUND') {
                    this.queue.unshift(eventData);
                    this._log('Event returned to queue (connection error)');
                }
                break;
            }
        }
        
        this.isProcessing = false;
        
        // Если появились новые элементы, запускаем обработку снова
        if (this.queue.length > 0) {
            setImmediate(() => this._processQueue());
        }
    }
    
    async _sendSync(payload) {
        try {
            const response = await axios.post(
                `${this.endpoint}/track`,
                payload,
                {
                    headers: {
                        'Content-Type': 'application/json',
                        'User-Agent': 'ErrorMonitor-SDK/1.0 (Node.js)',
                        ...this._authHeaders(),
                    },
                    timeout: 5000
                }
            );
            
            if (response.status === 200) {
                this._log('✅ Event sent successfully', { action: payload.action });
            } else {
                this._error('Failed to send event', { status: response.status, data: response.data });
            }
            
            return response;
        } catch (error) {
            if (error.response) {
                // Сервер ответил с ошибкой
                this._error('Server error', {
                    status: error.response.status,
                    data: error.response.data
                });
            } else if (error.request) {
                // Запрос был отправлен, но нет ответа
                this._error('No response from server', { endpoint: this.endpoint });
            } else {
                // Ошибка при настройке запроса
                this._error('Request error', error.message);
            }
            throw error;
        }
    }
    
    sendEvent(action, metadata = {}, pageUrl = null, context = {}) {
        try {
            const userId = typeof this.userIdFunc === 'function' 
                ? this.userIdFunc() 
                : 'anonymous';
            
            // Объединяем контексты
            const finalContext = {
                platform: 'backend',
                language: 'javascript',
                os_family: this.systemInfo.os_family,
                browser_family: 'node',
                ...this.context,
                ...context
            };
            
            // Формируем payload в формате API
            const payload = {
                project_id: this.projectId,
                action: action,
                timestamp: new Date().toISOString(),
                context: {
                    platform: finalContext.platform || 'backend',
                    language: finalContext.language || 'javascript',
                    os_family: finalContext.os_family || os.platform(),
                    browser_family: finalContext.browser_family || 'node'
                },
                meta: {
                    user_id: userId,
                    page_url: pageUrl || 'server-side',
                    sdk_version: '1.0.0',
                    runtime: process.version,
                    ...metadata
                }
            };
            
            // Добавляем всё из finalContext в meta (кроме основных полей)
            for (const [key, value] of Object.entries(finalContext)) {
                if (!['platform', 'language', 'os_family', 'browser_family'].includes(key)) {
                    payload.meta[`context_${key}`] = value;
                }
            }
            
            // Добавляем в очередь
            this.queue.push(payload);
            this._log('Event queued', { action, queueLength: this.queue.length });
            
            // Запускаем обработку очереди
            setImmediate(() => this._processQueue());
            
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
            ...metadata
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

    /**
     * Отправляет последние N строк файла на POST /logs/upload (фоново).
     * @param {string} filepath — абсолютный или относительный путь к файлу
     * @param {object} [options]
     * @param {number} [options.lines=50]
     * @param {string} [options.serverName]
     * @param {string} [options.serviceName]
     * @param {string} [options.environment]
     * @param {string} [options.errorGroupId]
     * @returns {boolean}
     */
    sendLogFile(filepath, options = {}) {
        return uploadLogFile(this, filepath, options);
    }
}

// Глобальный экземпляр
let _client = null;

module.exports = {
    /**
     * Инициализирует SDK
     * @param {Object} options - Опции инициализации
     * @param {string} options.endpoint - URL Collector API (например, "http://localhost:8000")
     * @param {string} options.projectId - Идентификатор проекта
     * @param {Function} options.userIdFunc - Функция для получения userId
     * @param {Object} options.context - Контекст по умолчанию
     * @param {boolean} options.debug - Режим отладки
     */
    initMonitor(options = {}) {
        _client = new MonitorClient(options);
        return _client;
    },
    
    /**
     * Отправляет событие
     * @param {string} action - Действие
     * @param {Object} metadata - Метаданные
     * @param {string} pageUrl - URL страницы
     */
    trackEvent(action, metadata = {}, pageUrl = null) {
        if (!_client) {
            throw new Error('❌ Call initMonitor() first');
        }
        _client.sendEvent(action, metadata, pageUrl);
    },
    
    /**
     * Отправляет информацию об исключении
     * @param {Error} error - Объект ошибки
     * @param {Object} metadata - Дополнительные метаданные
     * @param {string} pageUrl - URL страницы
     */
    captureException(error, metadata = {}, pageUrl = null) {
        if (!_client) {
            console.warn('⚠️ SDK not initialized, exception not captured');
            return;
        }
        _client.captureException(error, metadata, pageUrl);
    },
    
    /**
     * Устанавливает глобальный контекст
     * @param {Object} context - Контекст
     */
    setContext(context) {
        if (!_client) {
            throw new Error('❌ Call initMonitor() first');
        }
        _client.setContext(context);
    },
    
    /**
     * Очищает глобальный контекст
     */
    clearContext() {
        if (!_client) {
            throw new Error('❌ Call initMonitor() first');
        }
        _client.clearContext();
    },
    
    /**
     * Получает текущий клиент
     */
    getClient() {
        return _client;
    },

    /**
     * Отправка лог-файла (последние строки) на коллектор. Нужен initMonitor().
     * @param {string} filepath
     * @param {object} [options] — lines, serverName, serviceName, environment, errorGroupId
     */
    sendLogFile(filepath, options = {}) {
        if (!_client) {
            throw new Error('❌ Call initMonitor() first');
        }
        return uploadLogFile(_client, filepath, options);
    },
};