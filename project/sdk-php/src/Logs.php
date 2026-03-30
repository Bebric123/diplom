<?php

declare(strict_types=1);

namespace ErrorMonitor;

/**
 * POST /logs/upload: проверка полей и отправка (лимиты совпадают с коллектором).
 */
final class Logs
{
    /** Как в FastAPI LogFileCreate.content */
    public const MAX_CONTENT_BYTES = 2097152;

    public const MAX_FILENAME_LEN = 512;

    public const MAX_LABEL_LEN = 256;

    public const MAX_ENV_LEN = 64;

    public const MAX_ERROR_GROUP_ID_LEN = 64;

    public const MAX_LINES = 10_000_000;

    /**
     * Проверка тела запроса /logs/upload до отправки.
     *
     * @param array<string, mixed> $p
     *
     * @throws \InvalidArgumentException
     */
    public static function validateUploadPayload(array $p): void
    {
        $pid = $p['project_id'] ?? '';
        if (! is_string($pid) || $pid === '' || strlen($pid) > 64) {
            throw new \InvalidArgumentException('project_id must be a non-empty string, max 64 chars');
        }

        $filename = $p['filename'] ?? '';
        if (! is_string($filename) || $filename === '' || strlen($filename) > self::MAX_FILENAME_LEN) {
            throw new \InvalidArgumentException('filename must be 1–' . self::MAX_FILENAME_LEN . ' characters');
        }

        $content = $p['content'] ?? '';
        if (! is_string($content)) {
            throw new \InvalidArgumentException('content must be a string');
        }
        if (strlen($content) > self::MAX_CONTENT_BYTES) {
            throw new \InvalidArgumentException(
                'log content exceeds ' . self::MAX_CONTENT_BYTES . ' bytes (collector limit)'
            );
        }

        $linesSent = $p['lines_sent'] ?? null;
        if (! is_int($linesSent) || $linesSent < 0 || $linesSent > self::MAX_LINES) {
            throw new \InvalidArgumentException('lines_sent must be int 0..' . self::MAX_LINES);
        }

        $total = $p['total_lines'] ?? null;
        if ($total !== null) {
            if (! is_int($total) || $total < 0 || $total > self::MAX_LINES) {
                throw new \InvalidArgumentException('total_lines must be int 0..' . self::MAX_LINES . ' or null');
            }
        }

        foreach (['server_name', 'service_name'] as $k) {
            $v = $p[$k] ?? null;
            if ($v !== null && (! is_string($v) || strlen($v) > self::MAX_LABEL_LEN)) {
                throw new \InvalidArgumentException($k . ' max ' . self::MAX_LABEL_LEN . ' characters or null');
            }
        }

        $env = $p['environment'] ?? null;
        if ($env !== null && (! is_string($env) || strlen($env) > self::MAX_ENV_LEN)) {
            throw new \InvalidArgumentException('environment max ' . self::MAX_ENV_LEN . ' characters or null');
        }

        $eg = $p['error_group_id'] ?? null;
        if ($eg !== null && (! is_string($eg) || strlen($eg) > self::MAX_ERROR_GROUP_ID_LEN)) {
            throw new \InvalidArgumentException('error_group_id max ' . self::MAX_ERROR_GROUP_ID_LEN . ' characters or null');
        }
    }

    /**
     * Последние $lines строк файла → /logs/upload (через shutdown, как /track).
     *
     * @param array{server_name?: string|null, service_name?: string|null, environment?: string|null, error_group_id?: string|null} $options
     *
     * @return bool false если файл не найден, не читается или хвост пустой
     */
    public static function sendLogFile(Client $client, string $filepath, int $lines = 50, array $options = []): bool
    {
        if ($lines < 0) {
            throw new \InvalidArgumentException('lines must be >= 0');
        }

        if (! is_file($filepath) || ! is_readable($filepath)) {
            return false;
        }

        $raw = @file_get_contents($filepath);
        if ($raw === false || $raw === '') {
            return false;
        }

        if (strlen($raw) > self::MAX_CONTENT_BYTES) {
            throw new \InvalidArgumentException(
                'log file is larger than ' . self::MAX_CONTENT_BYTES . ' bytes; read tail in chunks or increase limit on collector'
            );
        }

        $norm = str_replace(["\r\n", "\r"], "\n", $raw);
        $allLines = explode("\n", $norm);
        $totalLines = count($allLines);

        $take = $lines > 0 ? min($lines, $totalLines) : $totalLines;
        $slice = $totalLines <= $take ? $allLines : array_slice($allLines, -$take);
        $content = implode("\n", $slice);

        if (trim($content) === '') {
            return false;
        }

        $linesSent = count($slice);
        $filename = basename($filepath);
        $serverName = $options['server_name'] ?? (gethostname() ?: 'unknown');
        $serviceName = $options['service_name'] ?? null;
        $environment = $options['environment'] ?? 'production';
        $errorGroupId = $options['error_group_id'] ?? null;

        $payload = [
            'project_id' => $client->getProjectId(),
            'filename' => $filename,
            'content' => $content,
            'lines_sent' => $linesSent,
            'total_lines' => $totalLines,
            'server_name' => $serverName,
            'service_name' => $serviceName,
            'environment' => $environment,
            'error_group_id' => $errorGroupId,
        ];

        self::validateUploadPayload($payload);

        $client->postLogsUploadJson(
            json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR)
        );

        return true;
    }
}
