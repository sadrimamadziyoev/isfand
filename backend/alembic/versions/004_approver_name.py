"""Record the independent reviewer's name alongside email and evidence."""

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"


def upgrade():
    op.add_column(
        "campaigns", sa.Column("approver_name", sa.String(200), nullable=True)
    )


def downgrade():
    op.drop_column("campaigns", "approver_name")
