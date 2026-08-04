from typing import Any, Literal

from pydantic import BaseModel, Field


PartType = Literal["bearing", "flange", "valve", "shaft", "gear", "screw", "coupling", "seal", "rocket"]


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


class ComponentRecommendationRequest(BaseModel):
    description: str = Field(min_length=2, max_length=5000)
    limit: int = Field(default=16, ge=1, le=32)
    use_ai: bool = True


class ComponentRecommendationResponse(BaseModel):
    component_ids: list[str]
    items: list[dict[str, Any]]
    parser: str
    limit: int
    missing_components: list[dict[str, Any]] = Field(default_factory=list)
    assembly_relations: list[dict[str, Any]] = Field(default_factory=list)
    capability: Literal["ready", "parametric_generation", "manual_rules_required"] = "ready"
    parser_detail: str | None = None


class GenerateResponse(BaseModel):
    id: str
    title: str
    part_type: PartType
    svg: str
    parameters: dict[str, Any]
    structural_parameters: dict[str, Any] = Field(default_factory=dict)
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
    component_resolution: dict[str, Any] | None = None
    assembly_report: dict[str, Any] | None = None
    quality_report: dict[str, Any] | None = None
    multiviews: dict[str, str] = Field(default_factory=dict)
    visual_regression: dict[str, Any] | None = None
    quality_score: dict[str, Any] | None = None
    semantic_assembly: dict[str, Any] | None = None
    review_status: Literal["pending", "approved", "rejected"] = "pending"


class YamlToStepRequest(BaseModel):
    spec_path: str = Field(min_length=1, max_length=500)
    reexport: bool = False


class FamilyMaterializeRequest(BaseModel):
    family_id: str = Field(min_length=2, max_length=100)
    parameters: dict[str, float] = Field(default_factory=dict)


class ComponentIngestRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2000)
    identity: dict[str, str]


class ReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=2, max_length=100)
    note: str = Field(default="", max_length=1000)
