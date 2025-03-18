from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserTemplate(BaseModel):
    name: Optional[str] = Field(None, nullable=True)
    data_limit: Optional[int] = Field(ge=0, default=None, description="data_limit can be 0 or greater")
    expire_duration: Optional[int] = Field(
        ge=0, default=None, description="expire_duration can be 0 or greater in seconds"
    )
    username_prefix: Optional[str] = Field(max_length=20, min_length=1, default=None)
    username_suffix: Optional[str] = Field(max_length=20, min_length=1, default=None)
    group_ids: list[int] | None = Field(default_factory=list)


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

    @field_validator("group_ids", mode="after")
    @classmethod
    def group_ids_validator(cls, v):
        if v and len(v) < 1:
            raise ValueError("you must select at least one group")
        return v


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
