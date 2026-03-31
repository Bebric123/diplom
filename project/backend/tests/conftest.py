"""
Обязательные переменные для импорта Settings до любых тестов.
Для интеграции: задайте TEST_DATABASE_URL (PostgreSQL) — тогда же подставится DATABASE_URL,
чтобы движок в src.core.database создался на тестовой БД при первом импорте моделей.
"""
from __future__ import annotations

import os

# Pydantic Settings: обязательные поля в .env при разработке
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "7200000000:FAKEtesttokenfortests")

# Отдельная тестовая БД (рекомендуется monitoring_test), не продакшен-Monitoring
_test_db = os.environ.get("TEST_DATABASE_URL")
if _test_db:
    os.environ["DATABASE_URL"] = _test_db
