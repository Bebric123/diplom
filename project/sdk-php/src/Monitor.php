<?php

declare(strict_types=1);

namespace ErrorMonitor;

/** Глобальный клиент после init_monitor(). */
final class Monitor
{
    private static ?Client $client = null;

    public static function init(Client $client): Client
    {
        self::$client = $client;

        return $client;
    }

    public static function get(): Client
    {
        if (self::$client === null) {
            throw new \RuntimeException('Call ErrorMonitor\\init_monitor() first');
        }

        return self::$client;
    }

    public static function hasClient(): bool
    {
        return self::$client !== null;
    }
}
