from typing import List
from fastapi import Depends, APIRouter
from app.db import Session, get_db
from app.models.admin import Admin
from app.models.user_template import UserTemplateCreate, UserTemplateModify, UserTemplateResponse
from app.dependencies import get_validated_user_template
from app.operation import OperatorType
from app.operation.user_template import UserTemplateOperation

router = APIRouter(tags=["User Template"], prefix="/api")

operator = UserTemplateOperation(OperatorType.API)


@router.post("/user_template", response_model=UserTemplateResponse)
async def add_user_template(
    new_user_template: UserTemplateCreate, db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin)
):
    """
    Add a new user template

    - **name** can be up to 64 characters
    - **data_limit** must be in bytes and larger or equal to 0
    - **expire_duration** must be in seconds and larger or equat to 0
    - **group_ids** list of group ids
    """
    return await operator.add_user_template(db, new_user_template, admin)


@router.get("/user_template/{template_id}", response_model=UserTemplateResponse)
def get_user_template_endpoint(
    dbuser_template: UserTemplateResponse = Depends(get_validated_user_template), _: Admin = Depends(Admin.get_current)
):
    """Get User Template information with id"""
    return dbuser_template


@router.put("/user_template/{template_id}", response_model=UserTemplateResponse)
async def modify_user_template(
    modify_user_template: UserTemplateModify,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
    dbuser_template: UserTemplateResponse = Depends(get_validated_user_template),
):
    """
    Modify User Template

    - **name** can be up to 64 characters
    - **data_limit** must be in bytes and larger or equal to 0
    - **expire_duration** must be in seconds and larger or equat to 0
    - **group_ids** list of group ids
    """
    return await operator.modify_user_template(db, dbuser_template, modify_user_template, admin)


@router.delete("/user_template/{template_id}")
async def remove_user_template(
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
    dbuser_template: UserTemplateResponse = Depends(get_validated_user_template),
):
    """Remove a User Template by its ID"""
    return await operator.remove_user_template(db, dbuser_template)


@router.get("/user_template", response_model=List[UserTemplateResponse])
async def get_user_templates(
    offset: int = None, limit: int = None, db: Session = Depends(get_db), admin: Admin = Depends(Admin.get_current)
):
    """Get a list of User Templates with optional pagination"""
    return await operator.get_user_templates(db, offset, limit, admin)
