from typing import List

from fastapi import APIRouter, Depends

from app import xray, logger
from app.db import Session, crud, get_db
from app.db.models import ProxyHost
from app.models.admin import Admin
from app.models.host import BaseHost, CreateHost
from app.utils import responses
from app.dependencies import get_host

router = APIRouter(tags=["Host"], prefix="/api/host", responses={401: responses._401, 403: responses._403})


@router.post("/", response_model=BaseHost)
def add_host(
    new_host: CreateHost,
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """
    add a new host

    **inbound_tag** must be available in one of xray config
    """
    db_host = crud.add_host(db, new_host)
    logger.info(f'Host "{db_host.id}" added')

    xray.hosts.update()

    return db_host


@router.put("/{host_id}", response_model=BaseHost, responses={404: responses._404})
def modify_host(
    modified_host: CreateHost,
    db_host: ProxyHost = Depends(get_host),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """
    modify host by **id**

    **inbound_tag** must be available in one of xray configs
    """

    db_host = crud.update_host(db, db_host, modified_host)
    logger.info(f'Host "{db_host.id}" modified')

    xray.hosts.update()

    return db_host


@router.delete("/{host_id}", responses={404: responses._404})
def remove_host(
    db_host: ProxyHost = Depends(get_host),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """
    remove host by **id**
    """

    crud.remove_host(db, db_host)
    logger.info(f'Host "{db_host.id}" deleted')

    xray.hosts.update()

    return {}


@router.get("/{host_id}", response_model=BaseHost)
def get_host(
    db_host: BaseHost = Depends(get_host),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """
    get host by **id**
    """

    return db_host


@router.get("s", response_model=List[BaseHost])
def get_hosts(
    offset: int = 0,
    limit: int = 0,
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """
    Get proxy hosts.
    """
    return crud.get_hosts(db, offset, limit)


@router.put("s", response_model=List[BaseHost])
def modify_hosts(
    modified_hosts: List[CreateHost],
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """
    Modify proxy hosts and update the configuration.

    **host.id** will be replaced by index+1
    """
    for id, host in enumerate(modified_hosts, start=1):
        host.id = id

    crud.update_hosts(db, modified_hosts)

    xray.hosts.update()

    return crud.get_hosts(db)
