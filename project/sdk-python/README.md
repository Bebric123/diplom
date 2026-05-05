# error-monitor-sdk (Python)

Клиент для коллектора Error Monitor: `POST /track` (события, исключения) и `POST /logs/upload` (хвост лог-файла).

## Установка

Из клона монорепозитория:

```bash
pip install -e ./project/sdk-python
```

Из GitHub без полного клона:

```bash
pip install "git+https://github.com/Bebric123/diplom.git#subdirectory=project/sdk-python"
```

## Документация

Интерактивная страница на коллекторе: `/docs/sdk`. Примеры запуска: `examples/sdk-demos/python/`.

## Примечания

- Windows, `MONITOR_URL` на 127.0.0.1: для `requests` отключается доверие к `HTTP(S)_PROXY` (`trust_env=False`), иначе POST на коллектор иногда идёт через прокси и отвечает 503 с пустым телом.
- Litestar, `ImportError: cannot import name 'MultipartSegment' from 'multipart'`: в venv стоит не тот пакет `multipart`. Выполните `pip uninstall multipart` и `pip install python-multipart` (см. `examples/sdk-demos/python/requirements.txt`), затем снова `pip install -r requirements.txt`.
- Starlette: демо — ASGI, запуск `uvicorn 04_starlette_demo:app --host 127.0.0.1 --port 8012`, а не `python 04_starlette_demo.py` (так сервер не поднимается).
