"""product images

Revision ID: 8a3f6c2e9b1d
Revises: 55c14589c59c
Create Date: 2026-08-03 00:00:00.000000

"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8a3f6c2e9b1d"
down_revision: Union[str, Sequence[str], None] = "55c14589c59c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "product_images",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_product_images_id", "product_images", ["id"]
    )
    op.create_index(
        "ix_product_images_product_id", "product_images", ["product_id"]
    )

    # Backfill: give every existing product with an image_url a matching
    # row here so it shows up in the new multi-image list too.
    bind = op.get_bind()
    products = bind.execute(
        sa.text("SELECT id, image_url FROM products WHERE image_url IS NOT NULL AND image_url != ''")
    ).fetchall()
    if products:
        product_images = sa.table(
            "product_images",
            sa.column("id", sa.String()),
            sa.column("product_id", sa.String()),
            sa.column("image_url", sa.Text()),
            sa.column("position", sa.Integer()),
        )
        bind.execute(
            product_images.insert(),
            [
                {
                    "id": str(uuid.uuid4()),
                    "product_id": row.id,
                    "image_url": row.image_url,
                    "position": 0,
                }
                for row in products
            ],
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_product_images_product_id", table_name="product_images")
    op.drop_index("ix_product_images_id", table_name="product_images")
    op.drop_table("product_images")
