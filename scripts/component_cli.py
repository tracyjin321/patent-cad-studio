#!/usr/bin/env python3
"""CLI for ComponentSpec STEP/YAML conversion and port-based assembly."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.component_spec import (  # noqa: E402
    assemble, inspect_step, load_spec, roundtrip_report, spec_to_step, step_to_spec, validate_spec,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="ComponentSpec v1.3 工具")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="检查 STEP 几何")
    inspect.add_argument("step", type=Path)
    convert = commands.add_parser("step-to-yaml", help="将任意 STEP 转为可搬移的 ComponentSpec YAML")
    convert.add_argument("step", type=Path)
    convert.add_argument("output", type=Path)
    convert.add_argument("--id")
    convert.add_argument("--name")
    convert.add_argument("--type", default="generic")
    convert.add_argument("--no-copy-reference", action="store_true")
    convert.add_argument("--reference-name", help="复制后的基准文件名；正式图元库建议使用 reference.step")
    build = commands.add_parser("yaml-to-step", help="从 YAML 恢复 STEP")
    build.add_argument("yaml", type=Path)
    build.add_argument("output", type=Path)
    build.add_argument("--no-checksum", action="store_true")
    build.add_argument("--reexport", action="store_true", help="经 OpenCascade 重导出为 AP242，而非原样复制")
    validate = commands.add_parser("validate", help="校验 YAML 结构、端口和 reference STEP")
    validate.add_argument("yaml", type=Path)
    roundtrip = commands.add_parser("roundtrip", help="执行 STEP→OpenCascade→STEP 几何一致性检查")
    roundtrip.add_argument("yaml", type=Path)
    roundtrip.add_argument("--output", type=Path)
    assembly = commands.add_parser("assemble", help="按 JSON 清单装配图元")
    assembly.add_argument("manifest", type=Path)
    assembly.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "inspect":
        result = inspect_step(args.step)
    elif args.command == "step-to-yaml":
        identity = {key: value for key, value in {"id": args.id, "name": args.name, "type": args.type}.items() if value}
        spec = step_to_spec(args.step, args.output, identity=identity, copy_reference=not args.no_copy_reference,
                            reference_filename=args.reference_name)
        result = {"yaml": str(args.output), "reference_step": spec["artifacts"]["reference_step"]["file"],
                  "identity": spec["identity"]}
    elif args.command == "yaml-to-step":
        result = spec_to_step(args.yaml, args.output, verify_checksum=not args.no_checksum, force_reexport=args.reexport)
    elif args.command == "validate":
        result = validate_spec(load_spec(args.yaml), spec_path=args.yaml)
        result["valid"] = not result["errors"]
        if not result["valid"]:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            raise SystemExit(1)
    elif args.command == "roundtrip":
        result = roundtrip_report(args.yaml, args.output)
        if not result["passed"]:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            raise SystemExit(1)
    else:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        entries = manifest["components"] if isinstance(manifest, dict) else manifest
        for item in entries:
            item["spec"] = str((args.manifest.parent / item["spec"]).resolve())
        result = assemble(entries, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
