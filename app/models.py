from typing import Any, Literal

from pydantic import BaseModel, Field


PartType = Literal["bearing", "flange", "valve", "shaft", "gear", "screw", "coupling", "seal"]


class GenerateRequest(BaseModel):
    description: str = Field(min_length=2, max_length=5000)
    part_type: PartType
    use_ai: bool = True
    core_elements: list[PartType] = Field(default_factory=list)
    component_ids: list[str] = Field(default_factory=list, max_length=32)


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
    spec_id: str
    spec_url: str
    generation_source: Literal["library", "cache", "generated"]
    spec_fingerprint: str
    core_elements: list[PartType] = Field(default_factory=list)
    selected_components: list[dict[str, Any]] = Field(default_factory=list)


class YamlToStepRequest(BaseModel):
    spec_path: str = Field(min_length=1, max_length=500)
    reexport: bool = False
