<?php

declare(strict_types=1);

namespace ErrorMonitor;

/**
 * HTTP-клиент коллектора: POST /track в формате, совместимом с Python/JS SDK.
 */
final class Client
{
    private string $endpoint;

    private string $projectId;

    private ?string $apiKey;

    /** @var callable(): string */
    private $userIdFunc;

    /** @var array<string, mixed> */
    private array $globalContext;

    public function __construct(
        string $endpoint,
        string $projectId = 'default-project',
        ?string $apiKey = null,
        ?callable $userIdFunc = null,
        array $globalContext = []
    ) {
        $this->endpoint = rtrim($endpoint, '/');
        $this->projectId = $projectId;
        $this->apiKey = $apiKey !== null && $apiKey !== '' ? trim($apiKey) : null;
        $this->userIdFunc = $userIdFunc ?? static fn (): string => 'anonymous';
        $this->globalContext = $globalContext;
    }

    /** @param array<string, mixed> $extra */
    public function mergeContext(array $extra): void
    {
        $this->globalContext = array_merge($this->globalContext, $extra);
    }

    /**
     * @param array<string, mixed> $metadata
     * @param array<string, mixed> $contextOverride
     */
    public function sendEvent(
        string $action,
        array $metadata = [],
        ?string $pageUrl = null,
        array $contextOverride = []
    ): void {
        try {
            $userId = ($this->userIdFunc)();
        } catch (\Throwable) {
            $userId = 'anonymous';
        }

        $finalContext = array_merge(
            [
                'platform' => 'backend',
                'language' => 'php',
                'os_family' => PHP_OS_FAMILY,
                'browser_family' => 'server',
            ],
            $this->globalContext,
            $contextOverride
        );

        $contextBlock = [
            'platform' => $finalContext['platform'] ?? 'backend',
            'language' => $finalContext['language'] ?? 'php',
            'os_family' => $finalContext['os_family'] ?? PHP_OS_FAMILY,
            'browser_family' => $finalContext['browser_family'] ?? 'server',
        ];

        $meta = array_merge(
            [
                'user_id' => $userId,
                'page_url' => $pageUrl ?? 'server-side',
                'sdk_version' => '1.0.0',
            ],
            $metadata
        );

        foreach ($finalContext as $key => $value) {
            if (! in_array($key, ['platform', 'language', 'os_family', 'browser_family'], true)) {
                $meta['context_' . $key] = $value;
            }
        }

        $payload = [
            'project_id' => $this->projectId,
            'action' => $action,
            'timestamp' => gmdate('c') . 'Z',
            'context' => $contextBlock,
            'meta' => $meta,
        ];

        $this->postTrackAsync($payload);
    }

    /**
     * @param array<string, mixed> $metadata
     */
    public function captureException(\Throwable $e, array $metadata = [], ?string $pageUrl = null): void
    {
        $this->sendEvent(
            'exception: ' . $e::class,
            array_merge(
                [
                    'exception_type' => $e::class,
                    'error_message' => $e->getMessage(),
                    'error_stack' => $e->getTraceAsString(),
                ],
                $metadata
            ),
            $pageUrl
        );
    }

    /**
     * Отправка в фоне через shutdown (не блокирует ответ пользователю, если возможно).
     *
     * @param array<string, mixed> $payload
     */
    private function postTrackAsync(array $payload): void
    {
        $endpoint = $this->endpoint;
        $apiKey = $this->apiKey;
        $json = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);

        register_shutdown_function(
            static function () use ($endpoint, $apiKey, $json): void {
                self::postJsonSync($endpoint . '/track', $json, $apiKey);
            }
        );
    }

    private static function postJsonSync(string $url, string $json, ?string $apiKey): void
    {
        if (! function_exists('curl_init')) {
            return;
        }
        $ch = curl_init($url);
        if ($ch === false) {
            return;
        }
        $headers = [
            'Content-Type: application/json',
            'User-Agent: ErrorMonitor-SDK/1.0 (PHP)',
        ];
        if ($apiKey !== null && $apiKey !== '') {
            $headers[] = 'Authorization: Bearer ' . $apiKey;
        }
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $json,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 5,
            CURLOPT_CONNECTTIMEOUT => 2,
        ]);
        curl_exec($ch);
        curl_close($ch);
    }
}
