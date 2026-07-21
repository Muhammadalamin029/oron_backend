"""guest checkout and bank transfer payments

Revision ID: 5f5da420a659
Revises: 957985caa3f3
Create Date: 2026-07-22 00:07:36.977005

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f5da420a659'
down_revision: Union[str, Sequence[str], None] = '957985caa3f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Guest-checkout accounts start with no password until they complete the
    # combined verify-email + set-password step.
    op.alter_column('users', 'hashed_password', existing_type=sa.String(), nullable=True)

    # Bank-transfer (Paystack Charge API / "Pay with Transfer") fields on Payment.
    # `payments.order_id` was never DB-uniquely-constrained, so the accompanying
    # Order.payment (1:1) -> Order.payments (1:many) relationship change on the
    # ORM side needs no schema change here.
    op.add_column('payments', sa.Column('method', sa.String(), nullable=True))
    op.execute("UPDATE payments SET method = 'redirect' WHERE method IS NULL")
    op.alter_column('payments', 'method', existing_type=sa.String(), nullable=False, server_default='bank_transfer')

    op.add_column('payments', sa.Column('bank_name', sa.String(), nullable=True))
    op.add_column('payments', sa.Column('account_number', sa.String(), nullable=True))
    op.add_column('payments', sa.Column('account_name', sa.String(), nullable=True))
    op.add_column('payments', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payments', sa.Column('meta', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('payments', 'meta')
    op.drop_column('payments', 'expires_at')
    op.drop_column('payments', 'account_name')
    op.drop_column('payments', 'account_number')
    op.drop_column('payments', 'bank_name')
    op.drop_column('payments', 'method')

    # NOTE: this will fail if any guest-checkout rows have hashed_password IS NULL —
    # those users would need a password backfilled (or deleted) before downgrading.
    op.alter_column('users', 'hashed_password', existing_type=sa.String(), nullable=False)
