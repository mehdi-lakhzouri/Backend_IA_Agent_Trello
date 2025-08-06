"""remove_reanalyse_from_ticket_analysis_history_only

Revision ID: 677466c3549a
Revises: cf9b8b0475bd
Create Date: 2025-08-05 17:54:12.123456

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '677466c3549a'
down_revision = 'cf9b8b0475bd'
branch_labels = None
depends_on = None


def upgrade():
    # Remove reanalyse column from ticket_analysis_history
    with op.batch_alter_table('ticket_analysis_history', schema=None) as batch_op:
        batch_op.drop_column('reanalyse')


def downgrade():
    # Add reanalyse column back to ticket_analysis_history
    with op.batch_alter_table('ticket_analysis_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reanalyse', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False, server_default=sa.text('FALSE')))
