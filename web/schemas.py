import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

JOB_ID_RE = re.compile(r"^j_[0-9]{8}_[0-9]{6}_[0-9a-f]{4}$")


class JobParams(BaseModel):
    context: str
    language: str = "english"
    research_mode: Literal["deep", "web", "none"] = "web"
    use_internet_image_search: bool = True
    fast_mode: bool = True
    enable_veo: bool = False
    veo_direction_by_director: bool = False

    @field_validator("context")
    @classmethod
    def context_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("context khong duoc rong")
        return value.strip()


class JobModels(BaseModel):
    MODEL_NAME: str | None = None
    IMAGE_GEN_MODEL: str | None = None
    TTS_MODEL: str | None = None


class CreateJobRequest(BaseModel):
    params: JobParams
    models: JobModels = Field(default_factory=JobModels)
    api_key: str | None = None
