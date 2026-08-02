"""broadcast messages

Revision ID: 5d3b215bc9d8
Revises: 4418dba0df49
Create Date: 2026-07-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5d3b215bc9d8"
down_revision: Union[str, Sequence[str], None] = "4418dba0df49"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "broadcast_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("sent_by_admin_id", sa.String(), nullable=True),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "include_customers", sa.Boolean(), nullable=True, server_default=sa.false()
        ),
        sa.Column("recipient_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("recipient_emails", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["sent_by_admin_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_broadcast_messages_id", "broadcast_messages", ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_broadcast_messages_id", table_name="broadcast_messages")
    op.drop_table("broadcast_messages")
