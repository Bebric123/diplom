-- Выполните один раз в PostgreSQL (тот же инстанс, что у коллектора).
-- UUID совпадает с дефолтом в примерах (MONITOR_PROJECT_ID).

INSERT INTO projects (id, name, description, is_active)
VALUES (
    '00000000-0000-4000-8000-000000000001'::uuid,
    'sdk-demo',
    'Тестовый проект для примеров SDK',
    true
)
ON CONFLICT (id) DO NOTHING;
