from typing import List, Optional

from pydantic import ConfigDict, BaseModel, Field


class UserTemplate(BaseModel):
    name: Optional[str] = Field(None, nullable=True)
    data_limit: Optional[int] = Field(ge=0, default=None, description="data_limit can be 0 or greater")
    expire_duration: Optional[int] = Field(
        ge=0, default=None, description="expire_duration can be 0 or greater in seconds"
    )
    username_prefix: Optional[str] = Field(max_length=20, min_length=1, default=None)
    username_suffix: Optional[str] = Field(max_length=20, min_length=1, default=None)
    group_ids: List[int] | None = []


class UserTemplateCreate(UserTemplate):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "my template 1",
                "username_prefix": None,
                "username_suffix": None,
                "group_ids": [1, 3, 5],
                "data_limit": 0,
                "expire_duration": 0,
            }
        }
    )


class UserTemplateModify(UserTemplate):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "my template 1",
                "username_prefix": None,
                "username_suffix": None,
                "group_ids": [1, 3, 5],
                "data_limit": 0,
                "expire_duration": 0,
            }
        }
    )


class UserTemplateResponse(UserTemplate):
    id: int

    model_config = ConfigDict(from_attributes=True)
