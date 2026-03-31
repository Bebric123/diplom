"""Удаление неиспользуемых таблиц и индексы для hot paths.

Revision ID: 20260330_01
Revises: 20260328_01
"""

from alembic import op

revision = "20260330_01"
down_revision = "20260328_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.events DROP CONSTRAINT IF EXISTS events_user_id_fkey;
        ALTER TABLE public.events DROP COLUMN IF EXISTS user_id;
        """
    )
    op.execute("DROP TABLE IF EXISTS public.notifications CASCADE;")
    op.execute("DROP TABLE IF EXISTS public.audit_logs CASCADE;")
    op.execute("DROP TABLE IF EXISTS public.classification_cache CASCADE;")
    op.execute("DROP TABLE IF EXISTS public.users CASCADE;")

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_events_project_created
            ON public.events (project_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS ix_events_created_at ON public.events (created_at DESC);
        CREATE INDEX IF NOT EXISTS ix_events_error_group_id ON public.events (error_group_id)
            WHERE error_group_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS ix_error_tasks_error_group_id ON public.error_tasks (error_group_id);
        CREATE INDEX IF NOT EXISTS ix_error_tasks_project_created
            ON public.error_tasks (project_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS ix_log_files_project_created
            ON public.log_files (project_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS ix_error_groups_project_id ON public.error_groups (project_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS public.ix_events_project_created;
        DROP INDEX IF EXISTS public.ix_events_created_at;
        DROP INDEX IF EXISTS public.ix_events_error_group_id;
        DROP INDEX IF EXISTS public.ix_error_tasks_error_group_id;
        DROP INDEX IF EXISTS public.ix_error_tasks_project_created;
        DROP INDEX IF EXISTS public.ix_log_files_project_created;
        DROP INDEX IF EXISTS public.ix_error_groups_project_id;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.users (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
            external_id varchar NOT NULL,
            email_hash varchar,
            ip_address inet,
            first_seen_at timestamptz DEFAULT now(),
            last_seen_at timestamptz,
            UNIQUE (project_id, external_id)
        );
        ALTER TABLE public.events ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES public.users(id);
        CREATE TABLE IF NOT EXISTS public.notifications (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            event_id uuid NOT NULL REFERENCES public.events(id) ON DELETE CASCADE,
            error_group_id uuid REFERENCES public.error_groups(id),
            channel varchar NOT NULL,
            status varchar NOT NULL,
            recipient varchar,
            content text,
            external_id varchar,
            created_at timestamptz DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS public.audit_logs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id uuid REFERENCES public.projects(id),
            user_id uuid REFERENCES public.users(id),
            api_key_id uuid REFERENCES public.api_keys(id),
            action varchar NOT NULL,
            entity_type varchar,
            entity_id uuid,
            ip_address inet,
            details jsonb,
            created_at timestamptz DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS public.classification_cache (
            error_signature varchar PRIMARY KEY,
            result jsonb NOT NULL,
            confidence double precision,
            used_count integer DEFAULT 1,
            created_at timestamptz DEFAULT now(),
            updated_at timestamptz
        );
        """
    )
