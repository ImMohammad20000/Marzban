from functools import lru_cache
import asyncio

from GozargahNodeBridge import GozargahNode, create_node, Health, NodeType
from aiorwlock import RWLock

from app.db import GetDB, get_tls_certificate
from app.db.models import Node, NodeConnectionType
from app.node.user import serialize_user_for_node, backend_users
from app.models.user import UserResponse


@lru_cache(maxsize=None)
def get_tls():
    with GetDB() as db:
        tls = get_tls_certificate(db)
        return tls


type_map = {
    NodeConnectionType.rest: NodeType.rest,
    NodeConnectionType.grpc: NodeType.grpc,
}


class NodeManager:
    def __init__(self):
        self._nodes: dict[int, GozargahNode] = {}
        self._lock = RWLock()

    async def update_node(self, node: Node) -> GozargahNode:
        async with self._lock.writer_lock:
            old_node: GozargahNode | None = self._nodes.get(node.id, None)
            if old_node is not None:
                try:
                    await old_node.set_health(Health.INVALID)
                    await old_node.stop()
                except Exception:
                    pass
                finally:
                    del self._nodes[node.id]

            tls = get_tls()
            new_node = create_node(
                connection=type_map[node.connection_type],
                address=node.address,
                port=node.port,
                client_cert=tls.certificate,
                client_key=tls.key,
                server_ca=node.server_ca,
                max_logs=node.max_logs,
                extra={"id": node.id, "usage_coefficient": node.usage_coefficient},
            )

            self._nodes[node.id] = new_node

            return new_node

    async def remove_node(self, id: int) -> None:
        async with self._lock.writer_lock:
            old_node: GozargahNode | None = self._nodes.get(id, None)
            if old_node is not None:
                try:
                    await old_node.set_health(Health.INVALID)
                    await old_node.stop()
                except Exception:
                    pass
                finally:
                    del self._nodes[id]

    async def get_node(self, id: int) -> GozargahNode | None:
        async with self._lock.reader_lock:
            return self._nodes.get(id, None)

    async def get_nodes(self) -> dict[int, GozargahNode]:
        async with self._lock.reader_lock:
            return self._nodes

    async def get_healthy_nodes(self) -> list[tuple[int, GozargahNode]]:
        async with self._lock.reader_lock:
            nodes: list[tuple[int, GozargahNode]] = [
                (id, node) for id, node in self._nodes.items() if (await node.get_health() == Health.HEALTHY)
            ]
            return nodes

    async def get_broken_nodes(self) -> list[tuple[int, GozargahNode]]:
        async with self._lock.reader_lock:
            nodes: list[tuple[int, GozargahNode]] = [
                (id, node) for id, node in self._nodes.items() if (await node.get_health() == Health.BROKEN)
            ]
            return nodes

    async def get_not_connected_nodes(self) -> list[tuple[int, GozargahNode]]:
        async with self._lock.reader_lock:
            nodes: list[tuple[int, GozargahNode]] = [
                (id, node) for id, node in self._nodes.items() if (await node.get_health() == Health.NOT_CONNECTED)
            ]
            return nodes

    async def update_user(self, user: UserResponse, inbounds: list[str] = None):
        proto_user = serialize_user_for_node(user.id, user.username, user.proxy_settings, inbounds)

        async with self._lock.reader_lock:
            add_tasks = [node.update_user(proto_user) for node in self._nodes.values()]
            await asyncio.gather(*add_tasks, return_exceptions=True)

    async def remove_user(self, user: UserResponse):
        proto_user = serialize_user_for_node(user.id, user.username, user.proxy_settings)

        async with self._lock.reader_lock:
            remove_tasks = [node.update_user(proto_user) for node in self._nodes.values()]
            await asyncio.gather(*remove_tasks, return_exceptions=True)


manager: NodeManager = NodeManager()


__all__ = ["backend_users"]
