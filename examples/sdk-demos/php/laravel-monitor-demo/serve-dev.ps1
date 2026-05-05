# Встроенный PHP-сервер для Laravel без «кракозябр» в путях (Windows, кириллица в C:\Users\…\).
# Роутер передаётся относительным путём ..\server.php, а не абсолютным путём с Unicode.
# Запуск: .\serve-dev.ps1   (из каталога laravel-monitor-demo, или: powershell -File .\serve-dev.ps1)
$ErrorActionPreference = "Stop"
$public = Join-Path $PSScriptRoot "public"
if (-not (Test-Path (Join-Path $PSScriptRoot "server.php"))) {
  Write-Error "Нет server.php в корне проекта."
  exit 1
}
Set-Location $public
Write-Host "Сервер: http://127.0.0.1:8017  (CWD: public, роутер ..\\server.php)" -ForegroundColor Green
& php -S 127.0.0.1:8017 "..\server.php"
