import json
from uuid import uuid4, UUID
from enum import Enum

from pydantic import BaseModel, Field

from app.utils.system import random_password


class ProxyTypes(str, Enum):
    # proxy_type = protocol
    VMess = "vmess"
    VLESS = "vless"
    Trojan = "trojan"
    Shadowsocks = "shadowsocks"

    @property
    def settings_model(self):
        if self == self.VMess:
            return VMessSettings
        if self == self.VLESS:
            return VlessSettings
        if self == self.Trojan:
            return TrojanSettings
        if self == self.Shadowsocks:
            return ShadowsocksSettings


class ProxySettings(BaseModel, use_enum_values=True):
    @classmethod
    def from_dict(cls, proxy_type: ProxyTypes, _dict: dict):
        return ProxyTypes(proxy_type).settings_model.model_validate(_dict)

    def dict(self, *, no_obj=False, **kwargs):
        if no_obj:
            return json.loads(self.model_dump_json())
        return super().model_dump(**kwargs)


class VMessSettings(ProxySettings):
    id: UUID = Field(default_factory=uuid4)

    def revoke(self):
        self.id = str(uuid4())


class XTLSFlows(str, Enum):
    NONE = ""
    VISION = "xtls-rprx-vision"


class VlessSettings(ProxySettings):
    id: UUID = Field(default_factory=uuid4)
    flow: XTLSFlows = XTLSFlows.NONE

    def revoke(self):
        self.id = uuid4()


class TrojanSettings(ProxySettings):
    password: str = Field(default_factory=random_password)

    def revoke(self):
        self.password = random_password()


class ShadowsocksMethods(str, Enum):  # Already a str, Enum which is good
    AES_128_GCM = "aes-128-gcm"
    AES_256_GCM = "aes-256-gcm"
    CHACHA20_POLY1305 = "chacha20-ietf-poly1305"
    XCHACHA20_POLY1305 = "xchacha20-poly1305"


class ShadowsocksSettings(ProxySettings):
    password: str = Field(default_factory=random_password)
    method: ShadowsocksMethods = ShadowsocksMethods.CHACHA20_POLY1305

    def revoke(self):
        self.password = random_password()


class ProxyTable(BaseModel):
    vmess: VMessSettings = Field(default_factory=VMessSettings)
    vless: VlessSettings = Field(default_factory=VlessSettings)
    trojan: TrojanSettings = Field(default_factory=TrojanSettings)
    shadowsocks: ShadowsocksSettings = Field(default_factory=ShadowsocksSettings)

    def dict(self, *, no_obj=False, **kwargs):
        if no_obj:
            return json.loads(self.model_dump_json())
        return super().model_dump(**kwargs)
