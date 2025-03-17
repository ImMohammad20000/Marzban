from sqlalchemy.orm import load_only, joinedload

from GozargahNodeBridge import create_user, create_proxy

from app.db import GetDB, User
from app.db.models import UserStatus,  ProxyInbound


def serialize_user_for_node(user: User, inbounds: list[str] = None):
    user_settings = user.proxy_settings

    vmess_settings = user_settings.get("vmess", {})
    vless_settings = user_settings.get("vless", {})
    trojan_settings = user_settings.get("trojan", {})
    shadowsocks_settings = user_settings.get("shadowsocks", {})

    return create_user(
        f"{user.id}.{user.username}",
        create_proxy(
            vmess_id=vmess_settings.get("id"),
            vless_id=vless_settings.get("id"),
            vless_flow=vless_settings.get("flow"),
            trojan_password=trojan_settings.get("password"),
            shadowsocks_password=shadowsocks_settings.get("password"),
            shadowsocks_method=shadowsocks_settings.get("method"),
        ),
        inbounds,
    )


async def backend_users(inbounds: list[str]):
    with GetDB() as db:
        query = (
            db.query(User)
            .options(
                load_only(User.id, User.username),
                joinedload(User.proxies).options(
                    load_only(Proxy.type, Proxy.settings),
                    joinedload(Proxy.excluded_inbounds).load_only(ProxyInbound.tag),
                ),
            )
            .filter(User.status.in_([UserStatus.active, UserStatus.on_hold]))
        )

        users = query.all()
        bridge_users: list = []

        for user in users:
            inbounds_list = user.inbounds(active_inbounds=inbounds)
            if len(inbounds_list) > 0:
                bridge_users.append(serialize_user_for_node(user, inbounds_list))

        return bridge_users
