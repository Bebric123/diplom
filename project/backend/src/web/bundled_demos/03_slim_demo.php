<?php

declare(strict_types=1);

/**
 * Slim 4 + обработчик ошибок с capture_exception.
 *
 * Запуск:
 *   cd examples/sdk-demos/php
 *   php -S 127.0.0.1:8016 03_slim_demo.php
 *
 * Проверка: curl http://127.0.0.1:8016/boom
 */
require __DIR__ . '/vendor/autoload.php';

use function ErrorMonitor\capture_exception;
use function ErrorMonitor\init_monitor;
use function ErrorMonitor\track_event;
use Psr\Http\Message\ResponseInterface;
use Psr\Http\Message\ServerRequestInterface;
use Slim\Factory\AppFactory;

$endpoint = getenv('MONITOR_URL') ?: 'http://127.0.0.1:8000';
$projectId = getenv('MONITOR_PROJECT_ID') ?: '00000000-0000-4000-8000-000000000001';
$rawKey = getenv('MONITOR_API_KEY');
$apiKey = ($rawKey !== false && $rawKey !== '') ? $rawKey : null;

init_monitor(
    $endpoint,
    $projectId,
    static fn (): string => 'slim-demo-user',
    ['demo' => 'php_slim'],
    $apiKey
);

$app = AppFactory::create();

$app->get('/health', function (ServerRequestInterface $request, ResponseInterface $response): ResponseInterface {
    $response->getBody()->write(json_encode(['ok' => true], JSON_THROW_ON_ERROR));

    return $response->withHeader('Content-Type', 'application/json; charset=utf-8');
});

$app->get('/ok', function (ServerRequestInterface $request, ResponseInterface $response): ResponseInterface {
    track_event('php_slim_ok', ['route' => '/ok'], null);
    $response->getBody()->write(json_encode(['message' => 'ok'], JSON_THROW_ON_ERROR));

    return $response->withHeader('Content-Type', 'application/json; charset=utf-8');
});

$app->get('/boom', function (): ResponseInterface {
    throw new RuntimeException('тестовая ошибка Slim для SDK');
});

$errorMiddleware = $app->addErrorMiddleware(true, true, true);
$errorMiddleware->setDefaultErrorHandler(
    function (
        ServerRequestInterface $request,
        Throwable $exception,
        bool $displayErrorDetails,
        bool $logErrors,
        bool $logErrorDetails
    ) use ($app): ResponseInterface {
        capture_exception($exception, ['path' => $request->getUri()->getPath()]);
        $response = $app->getResponseFactory()->createResponse(500);
        $response->getBody()->write('Internal Server Error');

        return $response->withHeader('Content-Type', 'text/plain; charset=utf-8');
    }
);

$app->run();
