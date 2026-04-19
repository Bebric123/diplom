<?php

declare(strict_types=1);

/**
 * Встроенный сервер PHP без Slim: маршруты /health, /ok, /boom.
 *
 * Запуск:
 *   cd examples/sdk-demos/php
 *   php -S 127.0.0.1:8015 02_builtin_server.php
 *
 * Проверка: curl http://127.0.0.1:8015/boom
 */
require __DIR__ . '/vendor/autoload.php';

use function ErrorMonitor\capture_exception;
use function ErrorMonitor\init_monitor;
use function ErrorMonitor\track_event;

$endpoint = getenv('MONITOR_URL') ?: 'http://127.0.0.1:8000';
$projectId = getenv('MONITOR_PROJECT_ID') ?: '07562d43-6bc3-49c3-acc1-46173c2fa8c8';
$rawKey = "DVVrT3GxU0n40FG8BfMaHvIbOjueO1a-oirVVJOMIkQ";
$apiKey = ($rawKey !== false && $rawKey !== '') ? $rawKey : null;

init_monitor(
    $endpoint,
    $projectId,
    static fn (): string => $_SERVER['HTTP_X_USER_ID'] ?? 'anonymous',
    ['demo' => 'php_builtin'],
    $apiKey
);

$uri = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
$uri = is_string($uri) ? $uri : '/';

if ($uri === '/favicon.ico') {
    http_response_code(404);
    exit;
}

try {
    if ($uri === '/health') {
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['ok' => true], JSON_THROW_ON_ERROR);
        exit;
    }

    if ($uri === '/ok') {
        header('Content-Type: application/json; charset=utf-8');
        track_event('php_builtin_ok', ['via' => 'builtin'], 'http://127.0.0.1:8015/ok');
        echo json_encode(['message' => 'ok'], JSON_THROW_ON_ERROR);
        exit;
    }

    if ($uri === '/boom') {
        throw new RuntimeException('тестовая ошибка PHP built-in server для SDK');
    }

    http_response_code(404);
    header('Content-Type: text/plain; charset=utf-8');
    echo "Not found. Try /health, /ok, /boom\n";
} catch (Throwable $e) {
    capture_exception($e, ['uri' => $uri], $_SERVER['REQUEST_URI'] ?? null);
    http_response_code(500);
    header('Content-Type: text/plain; charset=utf-8');
    echo "error (sent to monitor)\n";
}
