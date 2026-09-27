"""clear image paths that pointed at the instance disk

Revision ID: 0004_cloudinary_urls
Revises: 0003_partner_image
Create Date: 2026-09-27

Images used to be written to `media/` on the app server. Render's filesystem
is ephemeral, so every one of those files is already gone while the database
rows still point at them — the apps render a broken image or a placeholder.

Images now live on Cloudinary and the columns hold absolute https URLs, so
clear the dead local paths. Affected owners simply re-upload.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_cloudinary_urls"
down_revision: Union[str, Sequence[str], None] = "0003_partner_image"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("UPDATE partners SET image_url = NULL WHERE image_url LIKE '/media/%'")
    op.execute("UPDATE users SET avatar_url = NULL WHERE avatar_url LIKE '/media/%'")


def downgrade() -> None:
    """Downgrade schema.

    Nothing to restore: the files these paths referred to no longer exist.
    """
    pass
