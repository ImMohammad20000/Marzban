from app.operation import BaseOperator

from app.utils.logger import get_logger
from app.db import Session
from app.db.models import ProxyHost
from app.db.crud import add_host, get_or_create_inbound, get_host_by_id, remove_host, get_hosts
from app.models.host import CreateHost, BaseHost
from app.models.admin import Admin
from app.backend import hosts


logger = get_logger("host-operator")


class HostOperator(BaseOperator):
    async def get_hosts(
        self,
        db: Session,
        offset: int = 0,
        limit: int = 0,
    ) -> list[BaseHost]:
        return get_hosts(db=db, offset=offset, limit=limit)

    async def get_host(self, db: Session, host_id: int) -> ProxyHost:
        db_host = get_host_by_id(db, host_id)
        if db_host is None:
            self.raise_error(message="Host not found", code=404)
        return db_host

    async def add_host(
        self,
        db: Session,
        new_host: CreateHost,
        admin: Admin,
    ) -> BaseHost:
        inbound = get_or_create_inbound(db, new_host.inbound_tag)

        db_host = ProxyHost(inbound=inbound, **new_host.model_dump(exclude={"inbound_tag", "id"}))
        db_host = add_host(db, db_host)

        logger.info(f'Host "{db_host.id}" added by admin "{admin.username}"')

        hosts.update()

        return BaseHost.model_validate(db_host)

    async def modify_host(
        self,
        db: Session,
        host_id: int,
        modified_host: CreateHost,
        admin: Admin,
    ) -> BaseHost:
        db_host: ProxyHost = await self.get_host(db, host_id)
        if db_host.inbound_tag != modified_host.inbound_tag:
            db_host.inbound = get_or_create_inbound(db, modified_host.inbound_tag)

        # Get update data excluding inbound_tag
        update_data = modified_host.model_dump(
            exclude={"inbound_tag", "id"},
        )

        # Update attributes dynamically
        for key, value in update_data.items():
            setattr(db_host, key, value)

        db.commit()
        db.refresh(db_host)

        logger.info(f'Host "{db_host.id}" modified by admin "{admin.username}"')

        hosts.update()

        return BaseHost.model_validate(db_host)

    async def remove_host(
        self,
        db: Session,
        host_id: int,
        admin: Admin,
    ):
        db_host: ProxyHost = await self.get_host(db, host_id)
        remove_host(db, db_host)
        logger.info(f'Host "{db_host.id}" deleted by admin "{admin.username}"')

        hosts.update()

    async def update_hosts(self, db: Session, modified_hosts: list[CreateHost], admin: Admin) -> list[BaseHost]:
        for host in modified_hosts:
            update_data = host.model_dump(
                exclude={"inbound_tag", "id"},
            )

            old_host: ProxyHost | None = None
            if host.id is not None:
                old_host = get_host_by_id(db, host.id)

            inbound = get_or_create_inbound(db, host.inbound_tag)

            if old_host is None:
                new_host = ProxyHost(inbound=inbound, **update_data)
                db.add(new_host)
            else:
                for key, value in update_data.items():
                    setattr(old_host, key, value)

        db.commit()

        logger.info(f'Host\'s has been modified by admin "{admin.username}"')

        return get_hosts(db=db)
