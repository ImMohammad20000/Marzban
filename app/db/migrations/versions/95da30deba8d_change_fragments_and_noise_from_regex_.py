"""change fragments and noise from regex to json

Revision ID: 95da30deba8d
Revises: eaa9f30f983e
Create Date: 2025-02-26 21:54:13.977279

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision = '95da30deba8d'
down_revision = 'eaa9f30f983e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    def regex_to_json(table: sa.Table):
        for row in session.query(table.c.id, table.c.fragment_setting, table.c.noise_setting).all():
            fragment: str = row.fragment_setting
            noises: str = row.noise_setting
            fragment_json = sa.null()
            noises_settings_json = sa.null()
            if fragment:
                length, interval, packets = fragment.split(",")
                fragment_json = {"xray": {"packets": packets, "length": length, "interval": interval}}
            if noises:
                sn = noises.split("&")
                noises_settings_json = {"xray": []}
                for n in sn:
                    try:
                        tp, delay = n.split(",")
                        _type, packet = tp.split(":")
                        noises_settings_json["xray"].append(
                            {"type": _type, "packet": packet, "delay": delay})
                    except ValueError:
                        pass

            session.execute(
                table.update().where(table.c.id == row.id).values(
                    fragment_settings_temp=fragment_json, noise_settings_temp=noises_settings_json)
            )
    op.add_column('hosts', sa.Column('noise_settings_temp', sa.JSON(none_as_null=True), nullable=True))
    op.add_column('hosts', sa.Column('fragment_settings_temp', sa.JSON(none_as_null=True), nullable=True))

    try:
        with op.batch_alter_table('hosts') as batch_op:
            hosts_table = sa.Table('hosts', sa.MetaData(), autoload_with=bind)
            regex_to_json(hosts_table)

            batch_op.drop_column('noise_setting')
            batch_op.alter_column('noise_settings_temp', new_column_name='noise_settings')

            batch_op.drop_column('fragment_setting')
            batch_op.alter_column('fragment_settings_temp', new_column_name='fragment_settings')
            session.commit()
    finally:
        session.close()


def downgrade() -> None:
    pass
