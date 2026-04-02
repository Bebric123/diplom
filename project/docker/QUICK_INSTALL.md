# Установка без полного клона репозитория

Сборка образа всё равно требует каталог **`project/`** (контекст Docker — родитель `docker/`). Полный `git clone` не обязателен.

## 1. Архив с GitHub (без Git)

1. Откройте репозиторий → **Code** → **Download ZIP**.
2. Распакуйте архив; внутри будет папка вроде `diplom-main`.
3. Перейдите в `…/diplom-main/project/docker`, скопируйте `.env.example` в `.env`, заполните.
4. Настройте Open WebUI на хосте (или `ERROR_ANALYSIS_BACKEND=none`) и переменные `OPEN_WEBUI_*` в `.env`.
5. Выполните: `docker compose up -d --build`.

## 2. Мелкий клон Git (только последний коммит)

```bash
git clone --depth 1 https://github.com/Bebric123/diplom.git
cd diplom/project/docker
```

## 3. Sparse checkout (только backend + docker)

Уменьшает объём на диске; подходит для сервера, где нужен только коллектор.

```bash
git clone --filter=blob:none --sparse https://github.com/Bebric123/diplom.git
cd diplom
git sparse-checkout set project/backend project/docker
cd project/docker
```

Дальше — `.env` и `docker compose up -d --build` как обычно.

## 4. Только SDK в приложение

Клиентский SDK можно поставить без клона всего монорепозитория:

```bash
pip install "git+https://github.com/Bebric123/diplom.git#subdirectory=project/sdk-python"
```

Коллектор при этом поднимается отдельно (Docker или свой хост).
