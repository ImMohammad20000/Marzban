from app.db.models import Admin
from app.dependencies import get_validated_group
from app.operation import BaseOperator
from app.models.user_template import UserTemplateCreate, UserTemplateModify, UserTemplateResponse
from app.db import Session, crud
from sqlalchemy.exc import IntegrityError


class UserTemplateOperation(BaseOperator):
    async def add_user_template(
        self, db: Session, new_user_template: UserTemplateCreate, admin: Admin
    ) -> UserTemplateResponse:
        for group_id in new_user_template.group_ids:
            get_validated_group(group_id, admin, db)
        try:
            return crud.create_user_template(db, new_user_template)
        except IntegrityError:
            db.rollback()
            self.raise_error("Template by this name already exists", 409)

    async def modify_user_template(
        self, db: Session, dbuser_template: UserTemplateResponse, modify_user_template: UserTemplateModify, admin: Admin
    ) -> UserTemplateResponse:
        for group_id in modify_user_template.group_ids:
            get_validated_group(group_id, admin, db)
        try:
            return crud.update_user_template(db, dbuser_template, modify_user_template)
        except IntegrityError:
            db.rollback()
            self.raise_error("Template by this name already exists", 409)

    async def remove_user_template(self, db: Session, dbuser_template: UserTemplateResponse) -> None:
        crud.remove_user_template(db, dbuser_template)

    async def get_user_templates(
        self, db: Session, offset: int, limit: int, admin: Admin
    ) -> list[UserTemplateResponse]:
        return crud.get_user_templates(db, offset, limit)
