"""Component discovery, quarantined STEP ingestion, review, and version governance."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
from typing import Any
from urllib.parse import quote_plus, urlparse
from uuid import uuid4

import httpx
import yaml

from .component_library import LIBRARY, load_components
from .component_spec import roundtrip_report, step_to_spec, validate_spec


ROOT = Path(__file__).resolve().parent.parent
REVIEW_ROOT = ROOT / "generated" / "component-review"
BACKLOG_ROOT = ROOT / "generated" / "component-backlog"
AUDIT_LOG = ROOT / "generated" / "component-governance.jsonl"
MAX_STEP_BYTES = 50 * 1024 * 1024
SAFE_DOMAINS = {"step.parts", "www.step.parts"}


def discovery_links(query: str) -> list[dict[str, str]]:
    encoded = quote_plus(query.strip())
    return [
        {"provider": "local", "url": f"/api/components?q={encoded}", "purpose": "正式图元库"},
        {"provider": "step.parts", "url": f"https://www.step.parts/?search={encoded}", "purpose": "开源 STEP 图元"},
        {"provider": "national-standard", "url": f"https://std.samr.gov.cn/gb/search/gbQueryPage?searchText={encoded}", "purpose": "国家标准号与状态核验"},
    ]


def create_backlog(requirement: dict[str, Any]) -> dict[str, Any]:
    BACKLOG_ROOT.mkdir(parents=True, exist_ok=True)
    item_id = str(uuid4())
    record = {"id": item_id, "status": "open", "created_at": _now(), **requirement}
    (BACKLOG_ROOT / f"{item_id}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    _audit("backlog.created", record)
    return record


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit(event: str, payload: dict[str, Any]) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"event": event, "at": _now(), **payload}, ensure_ascii=False) + "\n")


def _validate_download_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("仅允许无凭据的 HTTPS STEP 地址")
    extra = {item.strip().casefold() for item in os.getenv("COMPONENT_SOURCE_DOMAINS", "").split(",") if item.strip()}
    if parsed.hostname.casefold() not in SAFE_DOMAINS | extra:
        raise ValueError("来源域名不在 COMPONENT_SOURCE_DOMAINS 允许列表")
    for result in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            raise ValueError("来源地址不能指向内网或本机")


def ingest_step_url(url: str, identity: dict[str, str], *, client: httpx.Client | None = None) -> dict[str, Any]:
    _validate_download_url(url)
    component_id = identity.get("id", "")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", component_id):
        raise ValueError("identity.id 必须是小写 kebab-case")
    if not identity.get("license"):
        raise ValueError("外部 STEP 入库必须声明 license")
    review_id = str(uuid4())
    directory = REVIEW_ROOT / review_id / component_id
    directory.mkdir(parents=True, exist_ok=False)
    source = directory / "download.step"
    owns_client = client is None
    remote = client or httpx.Client(follow_redirects=True, timeout=30)
    try:
        with remote.stream("GET", url, headers={"Accept": "model/step,application/step,*/*;q=.1"}) as response:
            response.raise_for_status()
            total = 0
            with source.open("wb") as stream:
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_STEP_BYTES:
                        raise ValueError("STEP 文件超过 50MB 限制")
                    stream.write(chunk)
    finally:
        if owns_client:
            remote.close()
    if not source.read_bytes()[:256].lstrip().startswith(b"ISO-10303-21;"):
        raise ValueError("下载内容不是 ISO-10303-21 STEP 文件")
    spec_path = directory / "component.yaml"
    spec = step_to_spec(source, spec_path, identity=identity, reference_filename="reference.step")
    source.unlink()
    spec["identity"].update({"status": "reviewed", "license": identity["license"], "description": f"从 {url} 下载并经隔离校验的 STEP 图元。"})
    spec["provenance"].update({"source_url": url, "source_type": "downloaded_step", "downloaded_at": _now(), "review_status": "pending_approval"})
    spec_path.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    validation = validate_spec(spec, spec_path=spec_path)
    roundtrip = roundtrip_report(spec_path)
    record = {"id": review_id, "component_id": component_id, "status": "pending_approval", "spec_path": str(spec_path), "validation": validation, "roundtrip": roundtrip,
              "source_sha256": hashlib.sha256((directory / "reference.step").read_bytes()).hexdigest(), "created_at": _now()}
    (REVIEW_ROOT / review_id / "review.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    _audit("ingestion.validated", {"review_id": review_id, "component_id": component_id, "url": url, "roundtrip": roundtrip["passed"]})
    if validation["errors"] or not roundtrip["passed"]:
        raise ValueError("STEP/YAML 双向校验失败")
    return record


def review_component(review_id: str, decision: str, reviewer: str, note: str = "") -> dict[str, Any]:
    record_path = REVIEW_ROOT / review_id / "review.json"
    if not record_path.is_file():
        raise KeyError(review_id)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record["status"] != "pending_approval":
        raise ValueError("该入库任务已经完成审核")
    if decision not in {"approve", "reject"}:
        raise ValueError("decision 必须是 approve 或 reject")
    if decision == "approve":
        source_dir = Path(record["spec_path"]).parent
        target = LIBRARY / record["component_id"]
        if target.exists():
            existing = yaml.safe_load((target / "component.yaml").read_text(encoding="utf-8"))
            incoming = yaml.safe_load((source_dir / "component.yaml").read_text(encoding="utf-8"))
            validate_version_transition(existing, incoming)
            archive = LIBRARY / ".versions" / record["component_id"] / existing["identity"]["version"]
            archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(target, archive, dirs_exist_ok=False)
            shutil.rmtree(target)
        shutil.copytree(source_dir, target)
        spec_path = target / "component.yaml"
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        spec["identity"].update({"status": "approved", "updated_at": _now()[:10]})
        spec["provenance"].update({"verified_by": reviewer, "verified_at": _now(), "review_note": note})
        spec_path.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
        _rebuild_catalog()
        load_components.cache_clear()
    record.update({"status": "approved" if decision == "approve" else "rejected", "reviewer": reviewer, "review_note": note, "reviewed_at": _now()})
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    _audit("ingestion.reviewed", {"review_id": review_id, "component_id": record["component_id"], "decision": decision, "reviewer": reviewer})
    return record


def validate_version_transition(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    def semver(value: str) -> tuple[int, int, int]:
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value or "")
        if not match:
            raise ValueError("图元版本必须采用 semantic versioning（x.y.z）")
        return tuple(int(part) for part in match.groups())

    old, new = semver(existing.get("identity", {}).get("version", "")), semver(incoming.get("identity", {}).get("version", ""))
    if new <= old:
        raise ValueError("新图元版本必须高于正式库版本")
    old_sha = existing.get("artifacts", {}).get("reference_step", {}).get("sha256")
    new_sha = incoming.get("artifacts", {}).get("reference_step", {}).get("sha256")
    if old_sha != new_sha and new[:2] == old[:2]:
        raise ValueError("几何变化必须提升 major 或 minor 版本，不能只提升 patch")


def _rebuild_catalog() -> None:
    from scripts.rebuild_component_catalog import build_catalog

    catalog = build_catalog(LIBRARY)
    (LIBRARY / "catalog.yaml").write_text(yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False), encoding="utf-8")
