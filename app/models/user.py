import re
import secrets
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.admin import Admin
from app.models.proxy import ProxySettings, ProxyTypes
from app.utils.jwt import create_subscription_token
from config import XRAY_SUBSCRIPTION_PATH, XRAY_SUBSCRIPTION_URL_PREFIX

USERNAME_REGEXP = re.compile(r"^(?=\w{3,32}\b)[a-zA-Z0-9-_@.]+(?:_[a-zA-Z0-9-_@.]+)*$")


class ReminderType(str, Enum):
    expiration_date = "expiration_date"
    data_usage = "data_usage"


class UserStatus(str, Enum):
    active = "active"
    disabled = "disabled"
    limited = "limited"
    expired = "expired"
    on_hold = "on_hold"


class UserStatusModify(str, Enum):
    active = "active"
    disabled = "disabled"
    on_hold = "on_hold"


class UserStatusCreate(str, Enum):
    active = "active"
    on_hold = "on_hold"


class UserDataLimitResetStrategy(str, Enum):
    no_reset = "no_reset"
    day = "day"
    week = "week"
    month = "month"
    year = "year"


class NextPlanModel(BaseModel):
    user_template_id: Optional[int] = None
    data_limit: Optional[int] = None
    expire: Optional[int] = None
    add_remaining_traffic: bool = False
    fire_on_either: bool = True
    model_config = ConfigDict(from_attributes=True)


class User(BaseModel):
    proxy_settings: Dict[ProxyTypes, ProxySettings] = {}
    expire: datetime | int | None = Field(None, nullable=True)
    data_limit: Optional[int] = Field(ge=0, default=None, description="data_limit can be 0 or greater")
    data_limit_reset_strategy: UserDataLimitResetStrategy = UserDataLimitResetStrategy.no_reset
    note: Optional[str] = Field(None, nullable=True)
    sub_updated_at: Optional[datetime] = Field(None, nullable=True)
    sub_last_user_agent: Optional[str] = Field(None, nullable=True)
    online_at: Optional[datetime] = Field(None, nullable=True)
    on_hold_expire_duration: Optional[int] = Field(None, nullable=True)
    on_hold_timeout: datetime | int | None = Field(None, nullable=True)
    group_ids: list[int] | None = Field(default_factory=list)
    auto_delete_in_days: Optional[int] = Field(None, nullable=True)

    next_plan: Optional[NextPlanModel] = Field(None, nullable=True)

    @field_validator("data_limit", mode="before")
    def cast_to_int(cls, v):
        if v is None:  # Allow None values
            return v
        if isinstance(v, float):  # Allow float to int conversion
            return int(v)
        if isinstance(v, int):  # Allow integers directly
            return v
        raise ValueError("data_limit must be an integer or a float, not a string")  # Reject strings

    @field_validator("proxy_settings", mode="before")
    def validate_proxies(cls, v, values, **kwargs):
        missing_protocols = {}
        for element in ProxyTypes:
            if element not in v:
                missing_protocols[element] = {}
        if missing_protocols:
            v.update(missing_protocols)
        return {proxy_type: ProxySettings.from_dict(proxy_type, v.get(proxy_type, {})) for proxy_type in v}

    @field_validator("username", check_fields=False)
    @classmethod
    def validate_username(cls, v):
        if not USERNAME_REGEXP.match(v):
            raise ValueError(
                "Username only can be 3 to 32 characters and contain a-z, 0-9, and underscores in between."
            )
        return v

    @field_validator("note", check_fields=False)
    @classmethod
    def validate_note(cls, v):
        if v and len(v) > 500:
            raise ValueError("User's note can be a maximum of 500 character")
        return v

    @field_validator("on_hold_expire_duration")
    @classmethod
    def validate_timeout(cls, v):
        # Check if expire is 0 or None and timeout is not 0 or None
        if v in (0, None):
            return None
        return v

    @field_validator("on_hold_timeout", check_fields=False)
    @classmethod
    def validator_on_hold_timeout(cls, value):
        if value == 0 or isinstance(value, datetime) or value is None:
            return value
        else:
            raise ValueError("on_hold_timeout can be datetime or 0")

    @field_validator("expire", check_fields=False)
    @classmethod
    def validator_expire(cls, value):
        if value == 0 or isinstance(value, datetime) or value is None:
            return value
        elif isinstance(value, int):
            return datetime.utcfromtimestamp(value)
        else:
            raise ValueError("expire can be datetime, timestamp or 0")


class UserCreate(User):
    username: str
    status: UserStatusCreate | None = None
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "user1234",
                "proxy_settings": {
                    "vmess": {"id": "35e4e39c-7d5c-4f4b-8b71-558e4f37ff53"},
                    "vless": {},
                },
                "group_ids": [1, 3, 5],
                "next_plan": {"data_limit": 0, "expire": 0, "add_remaining_traffic": False, "fire_on_either": True},
                "expire": 0,
                "data_limit": 0,
                "data_limit_reset_strategy": "no_reset",
                "status": "active",
                "note": "",
                "on_hold_timeout": "2023-11-03T20:30:00",
                "on_hold_expire_duration": 0,
            }
        }
    )

    @field_validator("status", mode="before")
    def validate_status(cls, status, values):
        on_hold_expire = values.data.get("on_hold_expire_duration")
        expire = values.data.get("expire")
        if status == UserStatusCreate.on_hold:
            if on_hold_expire == 0 or on_hold_expire is None:
                raise ValueError("User cannot be on hold without a valid on_hold_expire_duration.")
            if expire:
                raise ValueError("User cannot be on hold with specified expire.")
        return status

    @field_validator("group_ids", mode="after")
    @classmethod
    def group_ids_validator(cls, v):
        if not v and len(v) < 1:
            raise ValueError("you must select at least one group")
        return v


class UserModify(User):
    status: UserStatusModify | None = None
    data_limit_reset_strategy: UserDataLimitResetStrategy | None = None
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "proxy_settings": {
                    "vmess": {"id": "35e4e39c-7d5c-4f4b-8b71-558e4f37ff53"},
                    "vless": {},
                },
                "group_ids": [1, 3, 5],
                "next_plan": {"data_limit": 0, "expire": 0, "add_remaining_traffic": False, "fire_on_either": True},
                "expire": 0,
                "data_limit": 0,
                "data_limit_reset_strategy": "no_reset",
                "status": "active",
                "note": "",
                "on_hold_timeout": "2023-11-03T20:30:00",
                "on_hold_expire_duration": 0,
            }
        }
    )

    @field_validator("proxy_settings", mode="before")
    def validate_proxies(cls, v):
        return {proxy_type: ProxySettings.from_dict(proxy_type, v.get(proxy_type, {})) for proxy_type in v}

    @field_validator("status", mode="before")
    def validate_status(cls, status, values):
        on_hold_expire = values.data.get("on_hold_expire_duration")
        expire = values.data.get("expire")
        if status == UserStatusCreate.on_hold:
            if on_hold_expire == 0 or on_hold_expire is None:
                raise ValueError("User cannot be on hold without a valid on_hold_expire_duration.")
            if expire:
                raise ValueError("User cannot be on hold with specified expire.")
        return status


class UserResponse(User):
    id: int
    username: str
    status: UserStatus
    used_traffic: int
    lifetime_used_traffic: int = 0
    created_at: datetime
    subscription_url: str = ""
    admin: Optional[Admin] = None
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_subscription_url(self):
        if not self.subscription_url:
            salt = secrets.token_hex(8)
            url_prefix = (
                self.admin.sub_domain.replace("*", salt)
                if self.admin and self.admin.sub_domain
                else (XRAY_SUBSCRIPTION_URL_PREFIX).replace("*", salt)
            )
            token = create_subscription_token(self.username)
            self.subscription_url = f"{url_prefix}/{XRAY_SUBSCRIPTION_PATH}/{token}"
        return self

    @field_validator("proxy_settings", mode="before")
    def validate_proxies(cls, v, values, **kwargs):
        if isinstance(v, list):
            v = {p.type: p.settings for p in v}
        return super().validate_proxies(v, values, **kwargs)

    @field_validator("used_traffic", "lifetime_used_traffic", mode="before")
    def cast_to_int(cls, v):
        if v is None:  # Allow None values
            return v
        if isinstance(v, float):  # Allow float to int conversion
            return int(v)
        if isinstance(v, int):  # Allow integers directly
            return v
        raise ValueError("must be an integer or a float, not a string")  # Reject strings


class SubscriptionUserResponse(UserResponse):
    admin: Admin | None = Field(default=None, exclude=True)
    note: str | None = Field(None, exclude=True)
    auto_delete_in_days: int | None = Field(None, exclude=True)
    model_config = ConfigDict(from_attributes=True)


class UsersResponse(BaseModel):
    users: List[UserResponse]
    total: int


class UserUsageResponse(BaseModel):
    node_id: Union[int, None] = None
    node_name: str
    used_traffic: int

    @field_validator("used_traffic", mode="before")
    def cast_to_int(cls, v):
        if v is None:  # Allow None values
            return v
        if isinstance(v, float):  # Allow float to int conversion
            return int(v)
        if isinstance(v, int):  # Allow integers directly
            return v
        raise ValueError("must be an integer or a float")  # Reject strings


class UserUsagesResponse(BaseModel):
    username: str
    usages: List[UserUsageResponse]


class UsersUsagesResponse(BaseModel):
    usages: List[UserUsageResponse]
