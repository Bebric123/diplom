<?php

declare(strict_types=1);

namespace ErrorMonitor\Integrations\Laravel;

use ErrorMonitor\Client;
use ErrorMonitor\Monitor;
use Illuminate\Support\ServiceProvider;

/**
 * bootstrap/providers.php:
 *   ErrorMonitor\Integrations\Laravel\MonitorServiceProvider::class,
 *
 * .env: MONITOR_URL, MONITOR_PROJECT_ID, MONITOR_API_KEY
 *
 * app/Exceptions/Handler.php — в report():
 *   if (\ErrorMonitor\Monitor::hasClient()) {
 *       try { \ErrorMonitor\capture_exception($e); } catch (\Throwable) {}
 *   }
 */
final class MonitorServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->singleton(Client::class, function ($app): Client {
            return new Client(
                (string) env('MONITOR_URL', 'http://127.0.0.1:8000'),
                (string) env('MONITOR_PROJECT_ID', 'default-project'),
                ($k = env('MONITOR_API_KEY')) ? (string) $k : null,
                static function () use ($app): string {
                    if (! $app->bound('auth')) {
                        return 'anonymous';
                    }
                    try {
                        $u = $app['auth']->user();

                        return $u ? (string) $u->getAuthIdentifier() : 'anonymous';
                    } catch (\Throwable) {
                        return 'anonymous';
                    }
                },
                ['framework' => 'laravel']
            );
        });

        $this->app->afterResolving(Client::class, static function (Client $client): void {
            Monitor::init($client);
        });
    }
}
