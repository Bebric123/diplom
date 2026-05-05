<?php

declare(strict_types=1);

/**
 * Подхватывает examples/sdk-demos/php/.env без Composer (dotenv).
 * Поддерживает MONITOR_* и префикс VITE_ (как в фронтовом .env — копипаста из React/Vite).
 */
$__env = __DIR__ . DIRECTORY_SEPARATOR . '.env';
if (! is_file($__env)) {
    return;
}
foreach (file($__env, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
    $line = trim($line);
    if ($line === '' || str_starts_with($line, '#')) {
        continue;
    }
    if (! str_contains($line, '=')) {
        continue;
    }
    [$k, $v] = explode('=', $line, 2);
    $k = trim($k);
    $v = trim($v, " \t\"'");
    if (str_starts_with($k, 'VITE_')) {
        $k = substr($k, 5);
    }
    if (str_starts_with($k, 'MONITOR_') && $k !== '') {
        putenv("{$k}={$v}");
    }
}
unset($__env, $line, $k, $v);

// Сид: проект 0000… + ключ dev-demo-ingest-key (только если ключ в .env не задан)
$__pid = getenv('MONITOR_PROJECT_ID') ?: '00000000-0000-4000-8000-000000000001';
$__k = getenv('MONITOR_API_KEY');
if ($__k === false || $__k === null || $__k === '') {
    if ($__pid === '00000000-0000-4000-8000-000000000001') {
        putenv('MONITOR_API_KEY=dev-demo-ingest-key');
    }
}
unset($__pid, $__k);
