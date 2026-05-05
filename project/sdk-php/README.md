# error-monitor/sdk-php

PHP SDK для коллектора Error Monitor: `init_monitor`, `track_event`, `capture_exception`, `send_log_file`, интеграции Laravel / Symfony.

## Установка

Через path-репозиторий в `composer.json` (путь к каталогу `project/sdk-php` в вашем клоне):

```json
{
  "repositories": [{ "type": "path", "url": "../project/sdk-php" }],
  "require": { "error-monitor/sdk-php": "@dev" }
}
```

Пример готового `composer.json`: `examples/sdk-demos/php/composer.json`.

## Документация

`/docs/sdk` на коллекторе; демо: `examples/sdk-demos/php/`, Laravel — `examples/sdk-demos/php/laravel-demo/README.md`.

## Клиент и прокси (Windows)

Если `MONITOR_URL` указывает на **127.0.0.1** / **localhost**, для cURL в SDK **отключается** использование системного `HTTP(S)_PROXY` (иначе запросы к коллектору на loopback уходят в корпоративный прокси и вы получаете **503** с пустым телом). Для URL вне loopback (удалённый хост) поведение не меняется.
