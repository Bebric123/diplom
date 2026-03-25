// Fastify: перехват ошибок и опционально логирование ответов
const { getClient } = require('../index');

/**
 * @param {import('fastify').FastifyInstance} fastify
 * @param {object} [options]
 * @param {(req: import('fastify').FastifyRequest) => string} [options.userIdFunc]
 * @param {boolean} [options.captureErrors]
 * @param {boolean} [options.captureRequests]
 */
function enableFastifyIntegration(fastify, options = {}) {
    const client = getClient();

    if (!client) {
        console.warn('ErrorMonitor SDK not initialized. Call initMonitor() first.');
        return;
    }

    const {
        userIdFunc = (req) => req.ip || 'anonymous',
        captureErrors = true,
        captureRequests = false,
    } = options;

    fastify.addHook('onRequest', async (request) => {
        request.monitorUserId = userIdFunc(request);
        request.monitorStartMs = Date.now();
    });

    if (captureRequests) {
        fastify.addHook('onResponse', async (request, reply) => {
            const start = request.monitorStartMs || Date.now();
            const duration = Date.now() - start;
            client.sendEvent(
                `http: ${request.method} ${request.url}`,
                {
                    status_code: reply.statusCode,
                    duration_ms: duration,
                    user_id: request.monitorUserId,
                    path: request.url,
                },
                request.url,
            );
        });
    }

    if (captureErrors) {
        fastify.setErrorHandler(async (error, request, reply) => {
            client.captureException(
                error,
                {
                    user_id: request.monitorUserId,
                    url: request.url,
                    method: request.method,
                },
                request.url,
            );
            const statusCode = error.statusCode && error.statusCode < 600 ? error.statusCode : 500;
            reply.status(statusCode).send({
                error: error.name || 'Error',
                message: error.message,
            });
        });
    }

    console.log('Fastify integration enabled');
}

module.exports = { enableFastifyIntegration };
