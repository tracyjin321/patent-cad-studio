# 图元组件库

这里是项目中可参与 STEP/YAML 转换与装配的正式图元库。每个图元使用
`identity.id` 作为稳定目录名：

```text
component_library/
├── catalog.yaml
└── <component-id>/
    ├── component.yaml
    └── reference.step
```

- `component.yaml`：ComponentSpec v1.3 权威定义，保存参数、约束、端口、验证规则和来源。
- `reference.step`：固定规格的 B-Rep 几何基准，其 SHA-256 记录在 YAML 中。
- `catalog.yaml`：用于管理端、检索和批处理的轻量索引。

## 维护规则

1. 图元目录名和 `identity.id` 发布后保持稳定。
2. 替换 `reference.step` 后必须同步更新 YAML 中的 SHA-256 和实测几何数据。
3. 修改端口或参数后递增 `identity.version`，并执行校验及多轮往返测试。
4. 不要单独分发 YAML；`component.yaml` 与 `reference.step` 是一个交付单元。
5. 新增、删除或修改图元身份信息后，重新生成 `catalog.yaml`。

```bash
./.venv/bin/python scripts/component_cli.py validate \
  component_library/<component-id>/component.yaml

./.venv/bin/python scripts/multiround_roundtrip.py \
  --root component_library --rounds 5

./.venv/bin/python scripts/rebuild_component_catalog.py
```
