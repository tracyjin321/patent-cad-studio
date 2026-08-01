#!/usr/bin/env python3
"""Run chained ComponentSpec YAML/STEP round trips and write a Markdown report."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tempfile
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.component_spec import (  # noqa: E402
    _artifact_path,
    inspect_step,
    load_spec,
    spec_to_step,
    step_to_spec,
    validate_spec,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vector_delta(left: list[float], right: list[float]) -> float:
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(left, right)))


def compare_geometry(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    volume = abs(current["volume_mm3"] - baseline["volume_mm3"])
    relative_volume = volume / max(abs(baseline["volume_mm3"]), 1e-12)
    area = abs(current["surface_area_mm2"] - baseline["surface_area_mm2"])
    relative_area = area / max(abs(baseline["surface_area_mm2"]), 1e-12)
    bbox_delta = max(
        abs(float(a) - float(b))
        for key in ("min", "max", "size")
        for a, b in zip(baseline["bounding_box"][key], current["bounding_box"][key])
    )
    topology_delta = {
        key: current["topology"][key] - baseline["topology"][key]
        for key in ("solids", "shells", "faces", "edges", "vertices")
    }
    topology_equal = all(
        baseline["topology"][key] == current["topology"][key]
        for key in ("solids", "shells", "faces", "edges", "vertices")
    )
    engineering_topology_equal = all(
        baseline["topology"][key] == current["topology"][key]
        for key in ("solids", "shells", "faces")
    )
    engineering_equivalent = engineering_topology_equal and relative_volume <= 1e-6 and relative_area <= 1e-6 and bbox_delta <= 0.01
    return {
        "topology_equal": topology_equal,
        "topology_delta": topology_delta,
        "engineering_equivalent": engineering_equivalent,
        "volume_delta_mm3": volume,
        "volume_relative_delta": relative_volume,
        "surface_area_delta_mm2": area,
        "surface_area_relative_delta": relative_area,
        "bbox_max_delta_mm": bbox_delta,
        "center_delta_mm": vector_delta(baseline["center_of_mass"], current["center_of_mass"]),
        "passed": topology_equal and relative_volume <= 1e-6 and relative_area <= 1e-6 and bbox_delta <= 0.01,
    }


def semantic_snapshot(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "identity": {key: spec.get("identity", {}).get(key) for key in ("id", "name", "type", "subtype", "family")},
        "parameters": [item.get("name") for item in spec.get("parameters", [])],
        "ports": [
            {"id": item.get("id"), "type": item.get("type"), "frame": item.get("frame")}
            for item in spec.get("ports", [])
        ],
    }


def run_one(spec_path: Path, rounds: int, work: Path) -> dict[str, Any]:
    original_spec = load_spec(spec_path)
    source = _artifact_path(spec_path, original_spec)
    baseline = inspect_step(source)
    baseline_semantics = semantic_snapshot(original_spec)
    identity = {
        key: str(value) for key in ("id", "name", "name_en", "type", "subtype", "family")
        if (value := original_spec.get("identity", {}).get(key)) is not None
    }
    current_spec = spec_path
    round_results = []
    last_spec = original_spec
    part_dir = work / original_spec["identity"]["id"]
    part_dir.mkdir(parents=True, exist_ok=True)
    for number in range(1, rounds + 1):
        step_output = part_dir / f"round-{number}.step"
        yaml_output = part_dir / f"round-{number}.yaml"
        geometry = spec_to_step(current_spec, step_output, force_reexport=True)
        last_spec = step_to_spec(step_output, yaml_output, identity=identity, copy_reference=False,
                                 source_spec_path=current_spec)
        validation = validate_spec(last_spec, spec_path=yaml_output)
        comparison = compare_geometry(baseline, geometry)
        round_results.append({
            "round": number,
            "step_sha256": sha256(step_output),
            "step_bytes": step_output.stat().st_size,
            "yaml_bytes": yaml_output.stat().st_size,
            "yaml_valid": not validation["errors"],
            **comparison,
        })
        current_spec = yaml_output
    final_semantics = semantic_snapshot(last_spec)
    return {
        "path": str(spec_path.relative_to(ROOT)),
        "id": original_spec["identity"]["id"],
        "baseline": baseline,
        "rounds": round_results,
        "all_geometry_passed": all(item["passed"] for item in round_results),
        "all_engineering_equivalent": all(item["engineering_equivalent"] for item in round_results),
        "all_yaml_valid": all(item["yaml_valid"] for item in round_results),
        "step_bytes_original": source.stat().st_size,
        "step_bytes_final": round_results[-1]["step_bytes"],
        "step_byte_identical": sha256(source) == round_results[-1]["step_sha256"],
        "semantic_identity_preserved": baseline_semantics["identity"] == final_semantics["identity"],
        "semantic_parameters_preserved": baseline_semantics["parameters"] == final_semantics["parameters"],
        "semantic_ports_preserved": baseline_semantics["ports"] == final_semantics["ports"],
        "original_semantics": baseline_semantics,
        "final_semantics": final_semantics,
    }


def markdown(results: list[dict[str, Any]], rounds: int) -> str:
    passed = sum(item["all_geometry_passed"] for item in results)
    engineering_passed = sum(item["all_engineering_equivalent"] for item in results)
    strict_failures = [item for item in results if not item["all_geometry_passed"]]
    parameter_preserved = sum(item["semantic_parameters_preserved"] for item in results)
    port_preserved = sum(item["semantic_ports_preserved"] for item in results)
    lines = [
        "# ComponentSpec YAML / STEP 多轮往返一致性报告",
        "",
        f"- 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- 图元数量：{len(results)}",
        f"- 每个图元串联轮数：{rounds}",
        f"- 实际转换次数：{len(results) * rounds} 次 YAML→STEP + {len(results) * rounds} 次 STEP→YAML",
        f"- 几何一致性通过：{passed}/{len(results)}",
        f"- 工程几何等价通过：{engineering_passed}/{len(results)}",
        "- 判定阈值：主体拓扑一致、体积/面积相对偏差 ≤ 1e-6、包围盒最大偏差 ≤ 0.01 mm",
        "",
        "## 总结",
        "",
        "| 图元 | 严格拓扑 | 工程等价 | YAML有效 | 最大体积偏差 | 最大面积偏差 | 最大包围盒偏差(mm) | 最大质心偏差(mm) | STEP字节相同 | 参数语义 | 端口语义 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in results:
        rs = item["rounds"]
        lines.append(
            f"| {item['id']} | {'通过' if item['all_geometry_passed'] else '失败'} | "
            f"{'通过' if item['all_engineering_equivalent'] else '失败'} | "
            f"{'通过' if item['all_yaml_valid'] else '失败'} | {max(r['volume_relative_delta'] for r in rs):.3e} | "
            f"{max(r['surface_area_relative_delta'] for r in rs):.3e} | "
            f"{max(r['bbox_max_delta_mm'] for r in rs):.6g} | {max(r['center_delta_mm'] for r in rs):.6g} | "
            f"{'是' if item['step_byte_identical'] else '否'} | "
            f"{'保留' if item['semantic_parameters_preserved'] else '丢失'} | "
            f"{'保留' if item['semantic_ports_preserved'] else '变化'} |"
        )
    lines += [
        "",
        "## 结论",
        "",
        f"1. **工程几何稳定性**：{engineering_passed}/{len(results)} 个抽样图元满足实体、壳、面、体积和包围盒工程等价阈值。",
        f"2. **严格拓扑稳定性**：{passed}/{len(results)} 个图元的实体/壳/面/边/点计数完全一致；严格失败图元为："
        + ("、".join(item["id"] for item in strict_failures) if strict_failures else "无") + "。",
        "3. **文件字节不应作为重导出一致性标准**：OpenCascade 会重排 STEP 实体编号并重写头信息，因此重导出后 SHA-256 通常不同。未要求重导出时，reference_brep 路径仍使用原文件复制，可保持字节一致。",
        f"4. **STEP→YAML 的语义恢复存在边界**：参数语义保留 {parameter_preserved}/{len(results)}，端口语义保留 {port_preserved}/{len(results)}。普通 STEP B-Rep 不包含原 YAML 的参数定义、约束、预设和业务端口；原 YAML 必须作为权威 sidecar 保存。",
        "5. **颜色/产品名未纳入本轮通过判定**：当前导入使用 STEPControl_Reader，几何可稳定往返，但 AP214/AP242 的 XCAF 名称、层级、颜色需要 STEPCAFControl/XCAF 单独实现与验证。",
        "",
        "## 转换优化建议",
        "",
        "1. **P0—区分无损恢复与标准化重导出**：无位姿/协议变更时直接复制 `reference.step`，保证字节级无损；只有装配变换、修复或协议升级时才经 OpenCascade 重导出，避免无意义的累计拓扑扰动。",
        "2. **P0—让 YAML 成为权威 sidecar**：在 STEP 文件属性中嵌入 `component_id`、YAML SHA-256、schema/version；STEP→YAML 时优先关联原 sidecar，找不到时才生成 `generic/imported_step` 降级规范，并明确标记 `semantic_recovery: inferred`。",
        "3. **P1—采用 XCAF/STEPCAFControl**：当前 STEPControl 只覆盖几何。切换 XCAF 读写以保存产品名、装配树、颜色、图层和实例变换，并为这些语义增加独立往返断言。",
        "4. **P1—使用双层一致性签名**：发布门禁同时保存严格拓扑签名和工程几何签名。工程签名建议包含实体/壳/面数、体积、面积、包围盒、质心及容差；边/点因周期面边界拆分单独告警，不直接阻断。",
        "5. **P1—固定导出规范与修复流程**：统一 AP242、单位、写出精度和 OpenCascade 版本；重导出前固定执行 ShapeFix/SameParameter 流程，减少不同轮次的周期曲线拆边和实体编号波动。",
        "6. **P2—参数化图元使用显式生成器**：对轴承、齿轮、丝杆等建立 `generator_source + parameters`，不要尝试从普通 B-Rep 反推完整参数历史；用生成器输出与 reference STEP 做几何回归。",
        "",
        "## 每轮明细",
        "",
    ]
    for item in results:
        lines += [f"### {item['id']}", "", f"来源：`{item['path']}`", "",
                  "| 轮次 | 严格拓扑 | 工程等价 | Δ实体/壳/面/边/点 | 体积相对偏差 | 面积相对偏差 | 包围盒偏差(mm) | 质心偏差(mm) | STEP大小(bytes) |",
                  "|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for row in item["rounds"]:
            lines.append(
                f"| {row['round']} | {'是' if row['topology_equal'] else '否'} | "
                f"{'是' if row['engineering_equivalent'] else '否'} | "
                f"{row['topology_delta']['solids']}/{row['topology_delta']['shells']}/{row['topology_delta']['faces']}/{row['topology_delta']['edges']}/{row['topology_delta']['vertices']} | "
                f"{row['volume_relative_delta']:.3e} | {row['surface_area_relative_delta']:.3e} | "
                f"{row['bbox_max_delta_mm']:.6g} | "
                f"{row['center_delta_mm']:.6g} | {row['step_bytes']} |"
            )
        lines.append("")
    return "\n".join(lines)


def stratified_sample(specs: list[Path], size: int | None) -> list[Path]:
    if size is None or size >= len(specs):
        return specs
    groups: dict[str, deque[Path]] = defaultdict(deque)
    for path in specs:
        groups[str(load_spec(path).get("identity", {}).get("type", "unknown"))].append(path)
    selected: list[Path] = []
    keys = sorted(groups)
    while len(selected) < size and keys:
        next_keys = []
        for key in keys:
            if groups[key] and len(selected) < size:
                selected.append(groups[key].popleft())
            if groups[key]:
                next_keys.append(key)
        keys = next_keys
    return sorted(selected)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT / "component_library")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--report", type=Path, default=ROOT / "reports" / "step-yaml-multiround-report.md")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--sample-size", type=int, help="按 identity.type 分层抽样；默认验证全部图元")
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds 必须大于 0")
    specs = sorted(args.root.glob("*/component.yaml"))
    if not specs:
        parser.error(f"{args.root} 中没有 YAML")
    if args.sample_size is not None and args.sample_size < 1:
        parser.error("--sample-size 必须大于 0")
    specs = stratified_sample(specs, args.sample_size)
    with tempfile.TemporaryDirectory(prefix="component-multiround-") as directory:
        results = [run_one(path.resolve(), args.rounds, Path(directory)) for path in specs]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(markdown(results, args.rounds), encoding="utf-8")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.report)
    print(f"strict_topology_passed={sum(item['all_geometry_passed'] for item in results)}/{len(results)}")
    print(f"engineering_equivalent={sum(item['all_engineering_equivalent'] for item in results)}/{len(results)}")
    raise SystemExit(0 if all(item["all_engineering_equivalent"] and item["all_yaml_valid"] for item in results) else 1)


if __name__ == "__main__":
    main()
