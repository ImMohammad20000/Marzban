from app import backend
from app.operation import BaseOperator
from app.models.group import Group, GroupCreate, GroupModify, GroupsResponse
from app.db import Session, crud


class GroupOperation(BaseOperator):
    async def get_validated_group(self, group_id: int, db: Session) -> Group:
        dbgroup = crud.get_group_by_id(db, group_id)
        if not dbgroup:
            self.raise_error("Group not found", 404)
        return dbgroup

    async def check_inbound_tags(self, tags: list[str]) -> None:
        for tag in tags:
            if tag not in backend.config.inbounds_by_tag:
                self.raise_error(f"{tag} not found", 400)

    async def add_group(self, db: Session, new_group: GroupCreate) -> Group:
        await self.check_inbound_tags(new_group.inbound_tags)
        return crud.create_group(db, new_group)

    async def get_all_groups(self, db: Session, offset: int, limit: int) -> GroupsResponse:
        dbgroups, count = crud.get_group(db, offset, limit)
        return {"groups": dbgroups, "total": count}

    async def get_group(self, db: Session, group_id: int) -> Group:
        return await self.get_validated_group(group_id, db)

    async def modify_group(self, db: Session, dbgroup: Group, modified_group: GroupModify) -> Group:
        await self.check_inbound_tags(modified_group.inbound_tags)
        # TODO: add users to nodes
        return crud.update_group(db, dbgroup, modified_group)

    async def delete_group(self, db: Session, dbgroup: Group) -> None:
        crud.remove_group(db, dbgroup)
        # TODO: remove users from nodes
