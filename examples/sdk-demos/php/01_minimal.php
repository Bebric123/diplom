<?php

declare(strict_types=1);

/**
 * Событие без веб-фреймворка: init_monitor + track_event.
 * Запуск: php 01_minimal.php
 *
 * В PowerShell: задайте MONITOR_URL, MONITOR_PROJECT_ID, MONITOR_API_KEY
 * либо положите в этот каталог .env (см. .env.example). Префикс VITE_ от React тоже подхватится.
 *
 * По умолчанию: проект и ключ из db/seed_collector_security.sql (ingest), если сид применяли.
 */
require __DIR__ . '/bootstrap_local_env.php';
require __DIR__ . '/vendor/autoload.php';

use function ErrorMonitor\init_monitor;
use function ErrorMonitor\track_event;

$endpoint = getenv('MONITOR_URL') ?: 'http://127.0.0.1:8000';
$projectId = getenv('MONITOR_PROJECT_ID') ?: '00000000-0000-4000-8000-000000000001';
$rawKey = getenv('MONITOR_API_KEY');
$apiKey = $rawKey !== false && $rawKey !== null && $rawKey !== '' ? (string) $rawKey : null;

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
