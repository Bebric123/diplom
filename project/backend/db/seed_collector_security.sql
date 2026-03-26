-- Демо-проект и ingest API-ключ для локальной разработки.
-- Plaintext ключ: dev-demo-ingest-key  →  заголовок Authorization: Bearer dev-demo-ingest-key
-- или X-Api-Key: dev-demo-ingest-key
-- Хеш: SHA256(api_key_pepper || ключ) в hex; при пустом pepper совпадает с
-- python -c "import hashlib; print(hashlib.sha256(b'dev-demo-ingest-key').hexdigest())"
--
-- Включите проверку: COLLECTOR_REQUIRE_API_KEY=true
-- После применения сида задайте в клиентах MONITOR_API_KEY=dev-demo-ingest-key

INSERT INTO public.projects (id, name, description, is_active)
VALUES (
    '00000000-0000-4000-8000-000000000001',
    'SDK Demos',
    'Сид для примеров SDK',
    true
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.api_keys (id, project_id, name, hashed_key, scope, is_revoked)
VALUES (
    '10000000-0000-4000-8000-000000000001',
    '00000000-0000-4000-8000-000000000001',
    'demo-ingest',
    '137c0e2f0e7da8dbed613d291f3a30cb2bc84fce1655eefd13cc593ef6fe2460',
    ARRAY['ingest']::text[],
    false
)
ON CONFLICT (hashed_key) DO NOTHING;
