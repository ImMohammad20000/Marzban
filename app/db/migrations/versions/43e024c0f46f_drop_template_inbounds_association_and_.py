"""drop template_inbounds_association and exclude_inbounds_association

Revision ID: 43e024c0f46f
Revises: ed16dd5f1bc4
Create Date: 2024-12-21 19:06:29.575610

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '43e024c0f46f'
down_revision = 'ed16dd5f1bc4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('exclude_inbounds_association')
    op.drop_table('template_inbounds_association')
   # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('template_inbounds_association',
                    sa.Column('user_template_id', sa.INTEGER(), nullable=True),
                    sa.Column('inbound_tag', sa.VARCHAR(length=256), nullable=True),
                    sa.ForeignKeyConstraint(['inbound_tag'], ['inbounds.tag'], ),
                    sa.ForeignKeyConstraint(['user_template_id'], ['user_templates.id'], )
                    )
    op.create_table('exclude_inbounds_association',
                    sa.Column('proxy_id', sa.INTEGER(), nullable=True),
                    sa.Column('inbound_tag', sa.VARCHAR(length=256), nullable=True),
                    sa.ForeignKeyConstraint(['inbound_tag'], ['inbounds.tag'], ),
                    sa.ForeignKeyConstraint(['proxy_id'], ['proxies.id'], )
                    )
    # ### end Alembic commands ###