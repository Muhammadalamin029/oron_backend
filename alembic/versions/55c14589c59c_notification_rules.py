"""notification rules

Revision ID: 55c14589c59c
Revises: 2833914a09bc
Create Date: 2026-08-03 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "55c14589c59c"
down_revision: Union[str, Sequence[str], None] = "2833914a09bc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notification_rules",
        sa.Column("action", sa.String(), nullable=False),
        sa.Column(
            "notify_customers",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "notify_newsletter",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("action"),
    )
    op.create_index(
        "ix_notification_rules_action", "notification_rules", ["action"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_notification_rules_action", table_name="notification_rules")
    op.drop_table("notification_rules")
