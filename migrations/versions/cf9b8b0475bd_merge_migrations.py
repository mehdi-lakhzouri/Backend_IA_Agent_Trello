"""merge_migrations

Revision ID: cf9b8b0475bd
Revises: 0eb876a2c48c, board_name_reanalyse_001
Create Date: 2025-08-05 17:46:31.666498

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cf9b8b0475bd'
down_revision = ('0eb876a2c48c', 'board_name_reanalyse_001')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
