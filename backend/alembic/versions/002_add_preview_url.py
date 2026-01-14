"""Add preview_url to videos table

Revision ID: 002
Revises: 001
Create Date: 2026-01-12 03:57:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Add preview_url column to videos table
    op.add_column('videos', sa.Column('preview_url', sa.String(), nullable=True))


def downgrade():
    # Remove preview_url column from videos table
    op.drop_column('videos', 'preview_url')
