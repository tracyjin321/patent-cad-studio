from typing import Any, Literal

from pydantic import BaseModel, Field


PartType = Literal["bearing", "flange", "valve", "shaft", "gear", "screw", "coupling", "seal"]


class GenerateRequest(BaseModel):
    description: str = Field(min_length=2, max_length=5000)
    part_type: PartType
    field: str = "机械结构"
    use_ai: bool = True
    core_elements: list[PartType] = Field(default_factory=list)


class RecommendRequest(BaseModel):
    description: str = Field(min_length=2, max_length=5000)
    use_ai: bool = True


class RecommendResponse(BaseModel):
    elements: list[PartType]
    parser: str
    parser_detail: str | None = None


class GenerateResponse(BaseModel):
    id: str
    title: str
    part_type: PartType
    svg: str
    parameters: dict[str, Any]
    compliance: list[dict[str, Any]]
    parser: str
    parser_detail: str | None = None
    model: list[dict[str, Any]]
    step_url: str
    core_elements: list[PartType] = Field(default_factory=list)
