# Laravel + Error Monitor (PHP SDK)

Готовое дерево Laravel в монорепозиторий не коммитится: это сотни файлов и большой `vendor`. Демо — это **новый проект у себя локально** + несколько правок по шагам ниже.

Интеграция в SDK уже есть: `ErrorMonitor\Integrations\Laravel\MonitorServiceProvider` (singleton `Client`, `Monitor::init`, env `MONITOR_*`). Остаётся **пробрасывать исключения** в коллектор через `capture_exception` — в Laravel 11 это делается в `bootstrap/app.php`, в Laravel 10 — в `app/Exceptions/Handler.php`.

## Требования

- PHP ≥ 8.2 (Laravel 11), Composer
- Коллектор и переменные как в общем [README](../../README.md) корня `examples/sdk-demos`

## 1. Создать приложение

```bash
cd examples/sdk-demos/php   # или любая другая папка
composer create-project laravel/laravel:^11.0 laravel-monitor-demo
cd laravel-monitor-demo
```

## 2. Подключить SDK с path-репозиторием

В **`composer.json`** вашего Laravel-проекта добавьте репозиторий и зависимость. В **`url`** укажите путь от **корня Laravel-проекта** до каталога `project/sdk-php` в монорепозитории:

- проект в `…/examples/sdk-demos/php/laravel-monitor-demo` → обычно **`../../../../project/sdk-php`** (четыре уровня вверх до корня репозитория);
- если создали приложение внутри `laravel-demo/laravel-monitor-demo` → на один уровень глубже, путь на **`../../../../../project/sdk-php`**.

```json
"repositories": [
    {
        "type": "path",
        "url": "../../../../project/sdk-php"
    }
],
"require": {
    "error-monitor/sdk-php": "@dev"
}
```

Путь пересчитайте под своё расположение папок. Затем:

```bash
composer update error-monitor/sdk-php
```

## 3. Зарегистрировать провайдер

**Laravel 11:** в файле **`bootstrap/providers.php`** добавьте класс провайдера (рядом с `AppServiceProvider`):

```php
ErrorMonitor\Integrations\Laravel\MonitorServiceProvider::class,
```

Полный пример см. `snippets/providers.php`.

## 4. Отправка исключений в мониторинг

**Laravel 11** — в **`bootstrap/app.php`** внутри замыкания `withExceptions(function (Exceptions $exceptions) { ... })` вставьте код из **`snippets/report-exception.partial.php`** (блок `$exceptions->report(...)`).

**Laravel 10** — в **`app/Exceptions/Handler.php`** в методе `report()`:

```php
if (\ErrorMonitor\Monitor::hasClient()) {
    try {
        \ErrorMonitor\capture_exception($e);
    } catch (\Throwable) {
    }
}
```

(вызов — после `parent::report($e)` или вместо него, в зависимости от того, нужен ли стандартный лог.)

## 5. Переменные окружения

В **`.env`**:

```env
MONITOR_URL=http://127.0.0.1:8000
MONITOR_PROJECT_ID=ваш-uuid-после-register
MONITOR_API_KEY=ваш-ключ
```

## 6. Тестовый маршрут

В **`routes/web.php`**:

```php
Route::get('/boom', function () {
    throw new RuntimeException('тест Laravel + Error Monitor SDK');
});
```

## 7. Запуск

```bash
php artisan serve --host=127.0.0.1 --port=8017
```

Откройте `http://127.0.0.1:8017/boom` — событие должно уйти на коллектор (и далее в очередь/Telegram по настройкам проекта).

## Зачем не один файл, как Slim?

Laravel ожидает структуру приложения, автозагрузку, конфиг и провайдеры. Для Slim достаточно одного входного скрипта с `php -S`; для Laravel типичный путь — `composer create-project` + правки выше. Так демо остаётся актуальным при обновлении фреймворка без дублирования всего скелета в git.
