from fastapi import APIRouter, Depends, status
from app.db import Session, get_db
from app.dependencies import get_validated_group
from app.models.admin import Admin
from app.models.group import (
    Group,
    GroupCreate,
    GroupModify,
    GroupResponse,
    GroupsResponse,
)
from app.utils import responses
from app.operation.group import GroupOperation
from app.operation import OperatorType

router = APIRouter(
    prefix="/api",
    tags=["Groups"],
    responses={
        401: responses._401,
        403: responses._403,
    },
)

operator = GroupOperation(OperatorType.API)


@router.post(
    "/group",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new group",
    description="Creates a new group in the system. Only sudo administrators can create groups.",
    responses={
        201: {"description": "Group created successfully"},
        401: responses._401,
        403: responses._403,
    },
)
async def add_group(new_group: GroupCreate, db: Session = Depends(get_db), _: Admin = Depends(Admin.check_sudo_admin)):
    """
    Create a new group in the system.

    The group model has the following properties:
    - **name**: String (3-64 chars) containing only a-z and 0-9
    - **inbound_tags**: List of inbound tags that this group can access
    - **is_disabled**: Boolean flag to disable/enable the group

    Returns:
        GroupResponse: The created group data with additional fields:
            - **id**: Unique identifier for the group
            - **total_users**: Number of users in this group

    Raises:
        401: Unauthorized - If not authenticated
        403: Forbidden - If not sudo admin
    """
    return await operator.add_group(db, new_group)


@router.get(
    "/groups",
    response_model=GroupsResponse,
    summary="List all groups",
    description="Retrieves a paginated list of all groups in the system. Requires admin authentication.",
    responses={
        200: {"description": "List of groups retrieved successfully"},
        401: responses._401,
    },
)
async def get_all_groups(
    offset: int = None, limit: int = None, db: Session = Depends(get_db), _: Admin = Depends(Admin.get_current)
):
    """
    Retrieve a list of all groups with optional pagination.

    The response includes:
    - **groups**: List of GroupResponse objects containing:
        - **id**: Unique identifier
        - **name**: Group name
        - **inbound_tags**: List of allowed inbound tags
        - **is_disabled**: Group status
        - **total_users**: Number of users in group
    - **total**: Total count of groups

    Returns:
        GroupsResponse: List of groups and total count

    Raises:
        401: Unauthorized - If not authenticated
    """
    return await operator.get_all_groups(db, offset, limit)


@router.get(
    "/group/{group_id}",
    response_model=GroupResponse,
    summary="Get group details",
    description="Retrieves detailed information about a specific group by its ID.",
    responses={
        200: {"description": "Group details retrieved successfully"},
        404: {"description": "Group not found"},
    },
)
async def get_validated_group(dbgroup: Group = Depends(get_validated_group)):
    """
    Get a specific group by its **ID**.

    The response includes:
    - **id**: Unique identifier
    - **name**: Group name (3-64 chars, a-z, 0-9)
    - **inbound_tags**: List of allowed inbound tags
    - **is_disabled**: Group status
    - **total_users**: Number of users in group

    Returns:
        GroupResponse: The requested group data

    Raises:
        404: Not Found - If group doesn't exist
    """
    return dbgroup


@router.put(
    "/group/{group_id}",
    response_model=GroupResponse,
    summary="Update group",
    description="Updates an existing group's information. Only sudo administrators can modify groups.",
    responses={
        200: {"description": "Group updated successfully"},
        401: responses._401,
        403: responses._403,
        404: {"description": "Group not found"},
    },
)
async def modify_group(
    modified_group: GroupModify,
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
    dbgroup: Group = Depends(get_validated_group),
):
    """
    Update an existing group's information.

    The group model can be modified with:
    - **name**: String (3-64 chars) containing only a-z and 0-9
    - **inbound_tags**: List of inbound tags that this group can access
    - **is_disabled**: Boolean flag to disable/enable the group

    Returns:
        GroupResponse: The updated group data with additional fields:
            - **id**: Unique identifier for the group
            - **total_users**: Number of users in this group

    Raises:
        401: Unauthorized - If not authenticated
        403: Forbidden - If not sudo admin
        404: Not Found - If group doesn't exist
    """
    return await operator.modify_group(db, dbgroup, modified_group)


@router.delete(
    "/group/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete group",
    description="Deletes a group from the system. Only sudo administrators can delete groups.",
    responses={
        204: {"description": "Group deleted successfully"},
        401: responses._401,
        403: responses._403,
        404: {"description": "Group not found"},
    },
)
async def delete_group(
    db: Session = Depends(get_db),
    dbgroup: Group = Depends(get_validated_group),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """
    Delete a group by its **ID**.

    Returns:
        dict: Empty dictionary on successful deletion

    Raises:
        401: Unauthorized - If not authenticated
        403: Forbidden - If not sudo admin
        404: Not Found - If group doesn't exist
    """
    await operator.delete_group(db, dbgroup)
    return {}
