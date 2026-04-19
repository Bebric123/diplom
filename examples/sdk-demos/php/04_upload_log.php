<?php

declare(strict_types=1);

/**
 * Хвост лог-файла → POST /logs/upload (send_log_file + валидация в SDK).
 * Запуск: php 04_upload_log.php
 */
require __DIR__ . '/vendor/autoload.php';

use function ErrorMonitor\init_monitor;
use function ErrorMonitor\send_log_file;

$endpoint = getenv('MONITOR_URL') ?: 'http://127.0.0.1:8000';
$projectId = getenv('MONITOR_PROJECT_ID') ?: '07562d43-6bc3-49c3-acc1-46173c2fa8c8';
$rawKey = "DVVrT3GxU0n40FG8BfMaHvIbOjueO1a-oirVVJOMIkQ";
$apiKey = ($rawKey !== false && $rawKey !== '') ? $rawKey : null;

init_monitor(
    $endpoint,
    $projectId,
    null,
    ['demo' => 'php_logs'],
    $apiKey
);

$tmp = tempnam(sys_get_temp_dir(), 'emlog_');
if ($tmp === false) {
    fwrite(STDERR, "tempnam failed\n");
    exit(1);
}

file_put_contents($tmp, "2026-01-01 info: started\n2026-01-01 ERROR demo line for PHP SDK\n2026-01-01 WARN tail\n");

$ok = send_log_file($tmp, 10, ['service_name' => 'php-demo', 'environment' => 'demo']);
echo 'send_log_file: ', $ok ? 'queued' : 'skipped', "\n";
@unlink($tmp);

echo "Ждём 3 с (shutdown → curl /logs/upload)…\n";
sleep(3);
echo "Проверьте log_files и Celery.\n";
