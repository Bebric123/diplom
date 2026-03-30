<?php

declare(strict_types=1);

namespace ErrorMonitor;

/**
 * @param array<string, mixed> $context
 */
function init_monitor(
    string $endpoint,
    string $projectId = 'default-project',
    ?callable $userIdFunc = null,
    array $context = [],
    ?string $apiKey = null
): Client {
    $client = new Client($endpoint, $projectId, $apiKey, $userIdFunc, $context);

    return Monitor::init($client);
}

/**
 * @param array<string, mixed> $metadata
 */
function track_event(string $action, array $metadata = [], ?string $pageUrl = null): void
{
    Monitor::get()->sendEvent($action, $metadata, $pageUrl);
}

/**
 * @param array<string, mixed> $metadata
 */
function capture_exception(\Throwable $e, array $metadata = [], ?string $pageUrl = null): void
{
    Monitor::get()->captureException($e, $metadata, $pageUrl);
}

/**
 * @param array<string, mixed> $context
 */
function set_context(array $context): void
{
    Monitor::get()->mergeContext($context);
}

/**
 * Последние $lines строк лог-файла на POST /logs/upload (после init_monitor).
 *
 * @param array{server_name?: string|null, service_name?: string|null, environment?: string|null, error_group_id?: string|null} $options
 */
function send_log_file(string $filepath, int $lines = 50, array $options = []): bool
{
    return Logs::sendLogFile(Monitor::get(), $filepath, $lines, $options);
}
