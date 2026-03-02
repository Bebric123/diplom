// error-monitor-sdk/integrations/express.js
const { getClient } = require('../../index');

/**
 * Подключает мониторинг к Express приложению
 * @param {Object} app - Express приложение
 * @param {Object} options - Опции
 * @param {Function} options.userIdFunc - Функция для получения userId из request
 * @param {boolean} options.captureErrors - Перехватывать ошибки (default: true)
 * @param {boolean} options.captureRequests - Логировать запросы (default: false)
 */
function enableExpressIntegration(app, options = {}) {
    const client = getClient();
    
    if (!client) {
        console.warn('⚠️ ErrorMonitor SDK not initialized. Call initMonitor() first.');
        return;
    }
    
    const {
        userIdFunc = (req) => req.ip || req.connection.remoteAddress || 'anonymous',
        captureErrors = true,
        captureRequests = false
    } = options;
    
    // Middleware для добавления контекста запроса
    app.use((req, res, next) => {
        req.monitorContext = {
            url: req.url,
            method: req.method,
            path: req.path,
            query: req.query,
            params: req.params,
            headers: {
                'user-agent': req.headers['user-agent'],
                'referer': req.headers.referer,
                'content-type': req.headers['content-type']
            },
            ip: req.ip || req.connection.remoteAddress
        };
        
        // Добавляем пользователя в контекст
        try {
            req.userId = userIdFunc(req);
        } catch (error) {
            req.userId = 'anonymous';
        }
        
        next();
    });
    
    // Логирование запросов (опционально)
    if (captureRequests) {
        app.use((req, res, next) => {
            const startTime = Date.now();
            
            res.on('finish', () => {
                const duration = Date.now() - startTime;
                
                client.sendEvent(
                    `http: ${req.method} ${req.path}`,
                    {
                        status_code: res.statusCode,
                        duration_ms: duration,
                        user_id: req.userId,
                        ...req.monitorContext
                    },
                    req.url
                );
            });
            
            next();
        });
    }
    
    // Перехват ошибок
    if (captureErrors) {
        // Перехват синхронных ошибок
        app.use((err, req, res, next) => {
            client.captureException(
                err,
                {
                    user_id: req.userId,
                    ...req.monitorContext
                },
                req.url
            );
            
            // Пробрасываем дальше
            next(err);
        });
        
        // Перехват unhandled rejections
        process.on('unhandledRejection', (reason, promise) => {
            const error = reason instanceof Error ? reason : new Error(String(reason));
            client.captureException(
                error,
                {
                    type: 'unhandledRejection',
                    promise: String(promise)
                }
            );
        });
        
        // Перехват uncaught exceptions
        process.on('uncaughtException', (error) => {
            client.captureException(
                error,
                { type: 'uncaughtException' }
            );
            
            // Рекомендуется логировать и завершать процесс
            console.error('Uncaught Exception:', error);
            process.exit(1);
        });
    }
    
    console.log('✅ Express integration enabled');
}

module.exports = { enableExpressIntegration };