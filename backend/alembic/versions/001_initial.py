"""Initial schema, template seed, and forced tenant isolation."""

from pathlib import Path

from alembic import op
from app import models
from app.templates import TEMPLATES

revision = "001"
down_revision = None


def upgrade():
    bind = op.get_bind()
    bind.exec_driver_sql(Path(__file__).with_name("schema_001.sql").read_text())
    bind.execute(models.Template.__table__.insert(), TEMPLATES)
    for table in [
        "company_domains",
        "employees",
        "campaigns",
        "campaign_recipients",
        "tracking_events",
    ]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_scope ON {table} USING (company_id = current_setting('app.company_id', true)) WITH CHECK (company_id = current_setting('app.company_id', true))"
        )
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_scope ON audit_logs USING (company_id IS NULL OR company_id = current_setting('app.company_id', true)) WITH CHECK (company_id IS NULL OR company_id = current_setting('app.company_id', true))"
    )
    for table in ["employees", "campaigns"]:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_tenant_id UNIQUE(company_id,id)"
        )
    for table in ["campaign_recipients", "tracking_events"]:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_tenant_campaign FOREIGN KEY(company_id,campaign_id) REFERENCES campaigns(company_id,id) ON DELETE CASCADE"
        )
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_tenant_employee FOREIGN KEY(company_id,employee_id) REFERENCES employees(company_id,id) ON DELETE CASCADE"
        )
    # Only this constrained lookup crosses tenant boundaries for random public tokens.
    op.execute("""CREATE FUNCTION public.tracking_company(h text) RETURNS text
      LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public
      AS $$ SELECT company_id::text FROM public.campaign_recipients WHERE token_hash = h LIMIT 1 $$""")
    op.execute("REVOKE ALL ON FUNCTION public.tracking_company(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.tracking_company(text) TO awareguard")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO awareguard"
    )


def downgrade():
    op.execute("DROP FUNCTION IF EXISTS public.tracking_company(text)")
    op.drop_table("tracking_events")
    op.drop_table("campaign_recipients")
    op.drop_table("employees")
    op.drop_table("company_domains")
    op.drop_table("campaigns")
    op.drop_table("audit_logs")
    op.drop_table("admin_sessions")
    op.drop_table("email_templates")
    op.drop_table("companies")
    op.drop_table("admin_users")
