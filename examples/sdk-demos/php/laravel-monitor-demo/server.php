<?php

/**
 * Роутер для `php artisan serve` (тот же смысл, что vendor/laravel/.../resources/server.php).
 * Дублируем в корень проекта: на Windows с путём `C:\Users\…\Андрей\...` встроенный PHP-сервер
 * иногда не открывает скрипт из vendor по длинному пути; base_path('server.php') — обход.
 *
 * CWD задан как `public/`, getcwd() указывает на public.
 */
$publicPath = getcwd();

$uri = urldecode(
    parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH) ?? ''
);

if ($uri !== '/' && file_exists($publicPath.$uri)) {
    return false;
}

$formattedDateTime = date('D M j H:i:s Y');
$requestMethod = $_SERVER['REQUEST_METHOD'];
$remoteAddress = $_SERVER['REMOTE_ADDR'].':'.$_SERVER['REMOTE_PORT'];

file_put_contents('php://stdout', "[$formattedDateTime] $remoteAddress [$requestMethod] URI: $uri\n");

require_once $publicPath.'/index.php';
