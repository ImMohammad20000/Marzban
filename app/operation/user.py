import asyncio
import json

from sqlalchemy.exc import IntegrityError

from app.backend import config
from app.db import Session
from app.db.crud import (
    create_user,
    get_admin,
    get_user,
    get_user_template,
    remove_user,
    reset_user_data_usage,
    revoke_user_sub,
    update_user,
)
from app.db.models import NextPlan, User
from app.dependencies import get_validated_group
from app.models.admin import Admin
from app.models.user import UserCreate, UserModify, UserResponse, UserStatus
from app.node import manager as node_manager
from app.operation import BaseOperator
from app.utils.logger import get_logger

logger = get_logger("user-operator")


class UserOperator(BaseOperator):
    async def get_validated_user(self, db: Session, username: str, admin: Admin) -> User:
        db_user = get_user(db, username)
        if db_user is None:
            self.raise_error(message="User not found", code=404)

        if not (admin.is_sudo or (db_user.admin and db_user.admin.username == admin.username)):
            self.raise_error(message="You're not allowed", code=403)

        return db_user

    async def get_user_template(self, template_id: int, db: Session):
        dbuser_template = get_user_template(db, template_id)
        if not dbuser_template:
            self.raise_error(message="User Template not found", code=404)
        return dbuser_template

    async def add_user(self, db: Session, new_user: UserCreate, admin: Admin) -> UserResponse:
        if new_user.next_plan is not None and new_user.next_plan.user_template_id is not None:
            get_user_template(new_user.next_plan.user_template_id)

        user_data = new_user.model_dump(
            exclude={"next_plan", "expire", "proxy_settings", "group_ids"}, exclude_none=True
        )
        print("before", new_user.proxy_settings)
        all_groups = []
        if new_user.group_ids:
            for group_id in new_user.group_ids:
                db_group = get_validated_group(group_id, admin, db)
                all_groups.append(db_group)

        db_admin = get_admin(db, admin.username)
        db_user = User(
            **user_data,
            proxy_settings=new_user.proxy_settings.dict(no_obj=True),
            expire=(new_user.expire or None),
            admin=db_admin,
            groups=all_groups,
            next_plan=NextPlan(**new_user.next_plan.model_dump()) if new_user.next_plan else None,
        )
        print("after", db_user.proxy_settings)
        try:
            db_user = create_user(db, db_user)
        except IntegrityError:
            db.rollback()
            self.raise_error(message="User already exists", code=409)

        user = UserResponse.model_validate(db_user)

        asyncio.create_task(node_manager.update_user(user, inbounds=config.inbounds))

        logger.info(f'New user "{db_user.username}" with id "{db_user.id}" added by admin "{admin.username}"')

        return user

    async def modify_user(self, db: Session, username: str, modified_user: UserModify, admin: Admin) -> UserResponse:
        db_user: User = await self.get_validated_user(db, username, admin)

        if modified_user.next_plan is not None and modified_user.next_plan.user_template_id is not None:
            get_user_template(modified_user.next_plan.user_template_id)

        old_status = db_user.status
        logger.info(modified_user.proxy_settings)
        db_user = update_user(db, db_user, modified_user)
        user = UserResponse.model_validate(db_user)

        if db_user.status in (UserStatus.active, UserStatus.on_hold):
            await node_manager.update_user(db_user, inbounds=config.inbounds)
        else:
            await node_manager.remove_user(db_user)

        logger.info(f'User "{user.username}" with id "{db_user.id}" modified by admin "{admin.username}"')

        if user.status != old_status:
            logger.info(f'User "{db_user.username}" status changed from "{old_status.value}" to "{user.status.value}"')

        return user

    async def remove_user(self, db: Session, username: str, admin: Admin):
        db_user: User = self.get_validated_user(db, username, admin)

        remove_user(db, db_user)
        asyncio.create_task(node_manager.remove_user(UserResponse.model_validate(db_user)))

        logger.info(f'User "{db_user.username}" with id "{db_user.id}" deleted by admin "{admin.username}"')
        return {}

    async def reset_user_data_usage(self, db: Session, username: str, admin: Admin):
        db_user: User = self.get_validated_user(db, username, admin)

        db_user = reset_user_data_usage(db=db, db_user=db_user)
        if db_user.status in (UserStatus.active, UserStatus.on_hold):
            await node_manager.update_user(db_user, inbounds=config.inbounds)

        logger.info(f'User "{db_user.username}" usage was reset by admin "{admin.username}"')

        return {}

    async def revoke_user_sub(self, db: Session, username: str, admin: Admin):
        db_user: User = self.get_validated_user(db, username, admin)

        db_user = revoke_user_sub(db=db, db_user=db_user)

        if db_user.status in (UserStatus.active, UserStatus.on_hold):
            await node_manager.update_user(db_user, inbounds=config.inbounds)

        logger.info(f'User "{db_user.username}" subscription was revoked by admin "{admin.username}"')

        return {}
