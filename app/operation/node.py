import asyncio

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from GozargahNodeBridge import GozargahNode, NodeAPIError

from app.operation import BaseOperator
from app.models.node import NodeCreate, NodeResponse, NodeSettings, NodesUsageResponse, NodeModify, NodeStats
from app.models.admin import Admin
from app.db.models import Node, NodeStatus
from app.db.crud import (
    create_node,
    get_node_by_id,
    update_node_status,
    get_nodes,
    remove_node,
    get_nodes_usage,
    update_node,
    get_user,
)
from app.db.base import GetDB
from app.backend import config
from app.node import get_tls, backend_users, manager as node_manager
from app.utils.logger import get_logger


logger = get_logger("node-operator")


class NodeOperator(BaseOperator):
    async def get_node_settings(self) -> NodeSettings:
        return NodeSettings(certificate=get_tls().certificate)

    async def get_node(self, db: Session, node_id: int) -> Node:
        """Dependency: Fetch node or return not found error."""
        db_node = get_node_by_id(db, node_id)
        if not db_node:
            self.raise_error(message="Node not found", code=404)
        return db_node

    async def get_db_node(self, db: Session, node_id: Node) -> NodeResponse:
        return NodeResponse.model_validate(await self.get_node(db=db, node_id=node_id))

    async def get_db_nodes(self, db: Session, offset: int | None, limit: int | None) -> list[NodeResponse]:
        return get_nodes(db=db, offset=offset, limit=limit)

    async def connect_node(self, node_id: int) -> None:
        gozargah_node: GozargahNode | None = await node_manager.get_node(node_id)
        if gozargah_node is None:
            return

        with GetDB() as db:
            db_node = get_node_by_id(db, node_id)

            if db_node is None:
                return

            logger.info(f'Connecting to "{db_node.name}" node')
            update_node_status(db, db_node, NodeStatus.connecting)

            try:
                info = await gozargah_node.start(
                    config=config.to_json(),
                    backend_type=0,
                    users=await backend_users(inbounds=config.inbounds),
                    keep_alive=db_node.keep_alive,
                    timeout=10,
                )
                update_node_status(
                    db=db,
                    dbnode=db_node,
                    status=NodeStatus.connected,
                    xray_version=info.core_version,
                    node_version=info.node_version,
                )
                logger.info(
                    f'Connected to "{db_node.name}" node v{info.node_version}, xray run on v{info.core_version}'
                )
            except NodeAPIError as e:
                logger.error(f"Failed to connect node {db_node.name} with id {db_node.id}: {e.detail}")
                if e.code == -4:
                    return

                update_node_status(
                    db=db,
                    dbnode=db_node,
                    status=NodeStatus.error,
                    message=e.detail,
                )

    async def add_node(self, db: Session, new_node: NodeCreate, admin: Admin) -> NodeResponse:
        try:
            db_node = create_node(
                db,
                Node(
                    **new_node.model_dump(
                        exclude={"id"},
                    )
                ),
            )
        except IntegrityError:
            db.rollback()
            self.raise_error(message=f'Node "{new_node.name}" already exists', code=409)

        await node_manager.update_node(db_node)

        asyncio.create_task(self.connect_node(node_id=db_node.id))

        logger.info(f'New node "{db_node.name}" with id "{db_node.id}" added by admin "{admin.username}"')

        return NodeResponse.model_validate(db_node)

    async def modify_node(self, db: Session, node_id: Node, modified_node: NodeModify, admin: Admin) -> NodeResponse:
        db_node: Node = await self.get_node(db=db, node_id=node_id)

        node_data = modified_node.model_dump(
            exclude={"id"},
            exclude_none=True,
        )

        for key, value in node_data.items():
            setattr(db_node, key, value)

        if db_node.status == NodeStatus.disabled:
            db_node.xray_version = None
            db_node.message = None
        else:
            db_node.status = NodeStatus.connecting

        updated_node = update_node(db, db_node)

        if updated_node.status is NodeStatus.disabled:
            await node_manager.remove_node(updated_node.id)
        else:
            await node_manager.update_node(db_node)
            asyncio.create_task(self.connect_node(node_id=db_node.id))

        logger.info(f'Node "{db_node.name}" with id "{db_node.id}" modified by admin "{admin.username}"')

        return NodeResponse.model_validate(updated_node)

    async def remove_node(self, db: Session, node_id: Node, admin: Admin) -> None:
        db_node: Node = await self.get_node(db=db, node_id=node_id)

        await node_manager.remove_node(db_node.id)
        remove_node(db=db, db_node=db_node)

        logger.info(f'Node "{db_node.name}" with id "{db_node.id}" deleted by admin "{admin.username}"')

    async def restart_node(self, node_id: Node, admin: Admin) -> None:
        asyncio.create_task(self.connect_node(node_id))
        logger.info(f'Node "{node_id}" restarted by admin "{admin.username}"')

    async def restart_all_node(self, db: Session, admin: Admin) -> None:
        for db_node in get_nodes(db=db, enabled=True):
            await asyncio.create_task(self.connect_node(db_node.id))
        logger.info(f'All Node\'s restarted by admin "{admin.username}"')

    async def get_usage(self, db: Session, start: str = "", end: str = "") -> NodesUsageResponse:
        start, end = self.validate_dates(start, end)
        usages = get_nodes_usage(db, start, end)

        return {"usages": usages}

    async def get_logs(self, node_id: Node) -> asyncio.Queue:
        node = await node_manager.get_node(node_id)

        if node is None:
            self.raise_error(message="Node not found", code=404)

        try:
            logs_queue = await node.get_logs()
        except NodeAPIError as e:
            self.raise_error(message=e.detail, code=e.code)

        return logs_queue

    async def get_node_system_stats(self, node_id: Node) -> NodeStats:
        node = await node_manager.get_node(node_id)

        if node is None:
            self.raise_error(message="Node not found", code=404)

        try:
            stats = await node.get_system_stats()
        except NodeAPIError as e:
            self.raise_error(message=e.detail, code=e.code)

        if stats is None:
            self.raise_error(message="Stats not found", code=404)

        return NodeStats(
            mem_total=stats.mem_total,
            mem_used=stats.mem_used,
            cpu_cores=stats.cpu_cores,
            cpu_usage=stats.cpu_usage,
            incoming_bandwidth_speed=stats.incoming_bandwidth_speed,
            outgoing_bandwidth_speed=stats.outgoing_bandwidth_speed,
        )

    async def get_nodes_system_stats(self) -> dict[int, NodeStats | None]:
        nodes = await node_manager.get_healthy_nodes()
        stats_tasks = {id: asyncio.create_task(self._get_node_stats_safe(id)) for id, _ in nodes}

        await asyncio.gather(*stats_tasks.values(), return_exceptions=True)

        results = {}
        for node_id, task in stats_tasks.items():
            if task.exception():
                results[node_id] = None
            else:
                results[node_id] = task.result()

        return results

    async def _get_node_stats_safe(self, node_id: Node) -> NodeStats | None:
        """Wrapper method that returns None instead of raising exceptions"""
        try:
            return await self.get_node_system_stats(node_id)
        except Exception as e:
            logger.error(f"Error getting system stats for node {node_id}: {e}")
            return None

    async def get_user_online_stats_by_node(self, db: Session, node_id: Node, username: str) -> dict[int, int]:
        db_user = get_user(db, username=username)
        if db_user is None:
            self.raise_error(message="User not found", code=404)

        node = await node_manager.get_node(node_id)

        if node is None:
            self.raise_error(message="Node not found", code=404)

        try:
            stats = await node.get_user_online_stats(email=f"{db_user.id}.{db_user.username}")
        except NodeAPIError as e:
            self.raise_error(message=e.detail, code=e.code)

        if stats is None:
            self.raise_error(message="Stats not found", code=404)

        return {node_id: stats.value}

    async def get_user_ip_list_by_node(self, db: Session, node_id: Node, username: str) -> dict[int, dict[str, int]]:
        db_user = get_user(db, username=username)
        if db_user is None:
            self.raise_error(message="User not found", code=404)

        node = await node_manager.get_node(node_id)

        if node is None:
            self.raise_error(message="Node not found", code=404)

        try:
            stats = await node.get_user_online_ip_list(email=f"{db_user.id}.{db_user.username}")
        except NodeAPIError as e:
            self.raise_error(message=e.detail, code=e.code)

        if stats is None:
            self.raise_error(message="Stats not found", code=404)

        return {node_id: stats.ips}
