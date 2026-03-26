-- Добавить колонки троттлинга алертов для уже существующей БД (до обновления схемы).
-- Предпочтительно: Alembic (см. db/migrations/versions/ и `alembic upgrade head` в Docker).
-- Запасной вариант без Alembic — выполнить один раз, например:
--   docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f - < migrations_add_alert_throttle.sql
-- или вручную в psql.

ALTER TABLE public.error_groups
    ADD COLUMN IF NOT EXISTS alert_last_sent_at timestamp with time zone,
    ADD COLUMN IF NOT EXISTS alert_last_severity text;
