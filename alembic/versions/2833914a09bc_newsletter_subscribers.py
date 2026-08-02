"""newsletter subscribers

Revision ID: 2833914a09bc
Revises: 5d3b215bc9d8
Create Date: 2026-08-02 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2833914a09bc"
down_revision: Union[str, Sequence[str], None] = "5d3b215bc9d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "newsletter_subscribers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_newsletter_subscribers_id", "newsletter_subscribers", ["id"]
    )
    op.create_index(
        "ix_newsletter_subscribers_email",
        "newsletter_subscribers",
        ["email"],
        unique=True,
    )

    op.add_column(
        "broadcast_messages",
        sa.Column(
            "include_newsletter",
            sa.Boolean(),
            nullable=True,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("broadcast_messages", "include_newsletter")
    op.drop_index(
        "ix_newsletter_subscribers_email", table_name="newsletter_subscribers"
    )
    op.drop_index("ix_newsletter_subscribers_id", table_name="newsletter_subscribers")
    op.drop_table("newsletter_subscribers")
