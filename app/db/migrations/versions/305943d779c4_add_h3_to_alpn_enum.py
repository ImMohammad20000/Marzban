"""add h3 to alpn enum

Revision ID: 305943d779c4
Revises: 31f92220c0d0
Create Date: 2024-07-03 19:27:15.282711

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '305943d779c4'
down_revision = '31f92220c0d0'
branch_labels = None
depends_on = None


# Describing of enum
enum_name = "alpn"
temp_enum_name = f"temp_{enum_name}"
old_values = ("none", "h2", "http/1.1", "h2,http/1.1")
new_values = ("h3", "h3,h2", "h3,h2,http/1.1", *old_values)
# on downgrade
downgrade_from = ("h3", "h3,h2", "h3,h2,http/1.1", "")
downgrade_to = "none"
old_type = sa.Enum(*old_values, name=enum_name)
new_type = sa.Enum(*new_values, name=enum_name)
temp_type = sa.Enum(*new_values, name=temp_enum_name)


# Describing of table
table_name = "hosts"
column_name = "alpn"


def upgrade():
    # Create new enum type
    new_type.create(op.get_bind(), checkfirst=False)

    # Handle PostgreSQL specifically
    if isinstance(op.get_bind().dialect, postgresql.dialect):
        # Create a temporary text column
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column('alpn_new', sa.Text, nullable=True))
        
        # Copy data from old column to new column
        connection = op.get_bind()
        connection.execute(
            sa.text(f"UPDATE {table_name} SET alpn_new = alpn::text")
        )
        
        # Drop the old column and rename the new one
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column('alpn')
            batch_op.alter_column('alpn_new',
                new_column_name='alpn',
                type_=new_type,
                nullable=False,
                server_default=sa.text("'none'"),
                postgresql_using='alpn_new::alpn'
            )
    else:
        # For MySQL and SQLite, just modify the column type
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                column_name,
                existing_type=old_type,
                type_=new_type,
                existing_nullable=False
            )


def downgrade():
    # Create old enum type
    old_type.create(op.get_bind(), checkfirst=False)

    # Handle PostgreSQL specifically
    if isinstance(op.get_bind().dialect, postgresql.dialect):
        # Create a temporary text column
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column('alpn_old', sa.Text, nullable=True))
        
        # Copy data from current column to old column, replacing new values
        connection = op.get_bind()
        connection.execute(
            sa.text(f"UPDATE {table_name} SET alpn_old = CASE WHEN alpn::text IN {downgrade_from} THEN '{downgrade_to}' ELSE alpn::text END")
        )
        
        # Drop the current column and rename the old one
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column('alpn')
            batch_op.alter_column('alpn_old',
                new_column_name='alpn',
                type_=old_type,
                nullable=False,
                server_default=sa.text("'none'"),
                postgresql_using='alpn_old::alpn'
            )
    else:
        # For MySQL and SQLite, just modify the column type back
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                column_name,
                existing_type=new_type,
                type_=old_type,
                existing_nullable=False
            )

    # Drop the new enum type
    new_type.drop(op.get_bind(), checkfirst=False)
