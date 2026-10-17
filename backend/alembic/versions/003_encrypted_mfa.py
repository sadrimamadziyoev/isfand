"""Allow authenticated encryption envelopes for administrator MFA secrets."""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"


def upgrade():
    op.alter_column("admin_users", "mfa_secret", type_=sa.Text())


def downgrade():
    op.alter_column("admin_users", "mfa_secret", type_=sa.String(100))
