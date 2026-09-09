"""partner parlor image

Revision ID: 0003_partner_image
Revises: 0002_partner_auth
Create Date: 2026-09-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_partner_image"
down_revision: Union[str, Sequence[str], None] = "0002_partner_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "partners",
        sa.Column("image_url", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("partners", "image_url")
