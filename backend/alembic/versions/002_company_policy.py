"""Protect the company directory; platform admins may enumerate it."""

from alembic import op

revision = "002"
down_revision = "001"


def upgrade():
    op.execute("ALTER TABLE companies ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE companies FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY company_directory ON companies USING (id = current_setting('app.company_id', true) OR current_setting('app.platform_admin', true) = 'true') WITH CHECK (current_setting('app.platform_admin', true) = 'true')"
    )


def downgrade():
    op.execute("DROP POLICY company_directory ON companies")
    op.execute("ALTER TABLE companies DISABLE ROW LEVEL SECURITY")
