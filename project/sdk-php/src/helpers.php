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
