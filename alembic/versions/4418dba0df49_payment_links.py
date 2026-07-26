"""payment links

Revision ID: 4418dba0df49
Revises: 5f5da420a659
Create Date: 2026-07-23 19:25:06.118603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4418dba0df49'
down_revision: Union[str, Sequence[str], None] = '5f5da420a659'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'payment_links',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_payment_links_id', 'payment_links', ['id'])
    op.create_index('ix_payment_links_slug', 'payment_links', ['slug'], unique=True)

    op.create_table(
        'payment_link_items',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('payment_link_id', sa.String(), nullable=False),
        sa.Column('product_id', sa.String(), nullable=False),
        sa.Column('default_quantity', sa.Integer(), nullable=True, server_default='1'),
        sa.ForeignKeyConstraint(['payment_link_id'], ['payment_links.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_payment_link_items_id', 'payment_link_items', ['id'])

    op.add_column('orders', sa.Column('payment_link_id', sa.String(), nullable=True))
    op.create_foreign_key(
        'fk_orders_payment_link_id', 'orders', 'payment_links',
        ['payment_link_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_orders_payment_link_id', 'orders', type_='foreignkey')
    op.drop_column('orders', 'payment_link_id')
    op.drop_table('payment_link_items')
    op.drop_index('ix_payment_links_slug', table_name='payment_links')
    op.drop_index('ix_payment_links_id', table_name='payment_links')
    op.drop_table('payment_links')
