from fastapi import APIRouter, Depends

from app.db import Session, get_db
from app.models.admin import Admin
from app.models.host import BaseHost, CreateHost
from app.operation import OperatorType
from app.operation.host import HostOperator
from app.utils import responses


host_operator = HostOperator(operator_type=OperatorType.API)
router = APIRouter(tags=["Host"], prefix="/api/host", responses={401: responses._401, 403: responses._403})


@router.get("/{host_id}", response_model=BaseHost)
async def get_host(
    host_id: int,
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """
    get host by **id**
    """
    return await host_operator.get_host(db=db, host_id=host_id)


@router.get("s", response_model=list[BaseHost])
async def get_hosts(
    offset: int = 0,
    limit: int = 0,
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """
    Get proxy hosts.
    """
    return await host_operator.get_hosts(db=db, offset=offset, limit=limit)


@router.post("/", response_model=BaseHost)
async def add_host(
    new_host: CreateHost,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """
    add a new host

    **inbound_tag** must be available in one of xray config
    """
    return await host_operator.add_host(db, new_host=new_host, admin=admin)


@router.put("/{host_id}", response_model=BaseHost, responses={404: responses._404})
async def modify_host(
    host_id: int,
    modified_host: CreateHost,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """
    modify host by **id**

    **inbound_tag** must be available in one of xray configs
    """
    return await host_operator.modify_host(db, host_id=host_id, modified_host=modified_host, admin=admin)


@router.delete("/{host_id}", responses={404: responses._404})
async def remove_host(
    host_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """
    remove host by **id**
    """
    await host_operator.remove_host(db, host_id=host_id, admin=admin)
    return {}


@router.put("s", response_model=list[BaseHost])
async def modify_hosts(
    modified_hosts: list[CreateHost],
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """
    Modify proxy hosts and update the configuration.
    """
    return await host_operator.update_hosts(db=db, modified_hosts=modified_hosts, admin=admin)
