<?php

/**
 * Пример содержимого bootstrap/providers.php (Laravel 11).
 * Добавьте вторую строку к уже существующему AppServiceProvider.
 */
return [
    App\Providers\AppServiceProvider::class,
    ErrorMonitor\Integrations\Laravel\MonitorServiceProvider::class,
];
