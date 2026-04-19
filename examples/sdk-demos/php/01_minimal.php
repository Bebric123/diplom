<?php

declare(strict_types=1);

/**
 * Событие без веб-фреймворка: init_monitor + track_event.
 * Запуск: php 01_minimal.php
 */
require __DIR__ . '/vendor/autoload.php';

use function ErrorMonitor\init_monitor;
use function ErrorMonitor\track_event;

$endpoint = getenv('MONITOR_URL') ?: 'http://127.0.0.1:8000';
$projectId = getenv('MONITOR_PROJECT_ID') ?: '07562d43-6bc3-49c3-acc1-46173c2fa8c8';
$rawKey = "DVVrT3GxU0n40FG8BfMaHvIbOjueO1a-oirVVJOMIkQ";
$apiKey = ($rawKey !== false && $rawKey !== '') ? $rawKey : null;

init_monitor(
    $endpoint,
    $projectId,
    null,
    ['demo' => 'php_minimal'],
    $apiKey
);

track_event(
    'sdk_php_manual_test',
    ['note' => 'минимальный PHP демо'],
    'https://example.com/sdk-php-demo'
);

echo "Событие поставлено в очередь (отправка на shutdown). Ждём 2 с…\n";
sleep(2);
echo "Готово. Проверьте events на коллекторе и Celery.\n";
