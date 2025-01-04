"""add proxy_settings column to users table

Revision ID: ed4ea5ae1cf0
Revises: 02723eca82a4
Create Date: 2024-12-26 19:20:29.935417

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'ed4ea5ae1cf0'
down_revision = '02723eca82a4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('proxy_settings', sa.JSON(), server_default=sa.text("'{}'"), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'proxy_settings')
    # ### end Alembic commands ###