# 专图灵境

面向机械单零件的专利附图/CAD 方案生成工作台。支持轴承、法兰、阀门、轴系、齿轮、丝杠、联轴器、密封件。

生成链路采用 YAML-first 规格驱动：

1. Moonshot 从自然语言中提取结构参数（未配置或调用失败时自动使用本地解析）。
2. 将归一化参数写成 ComponentSpec `parametric_brep` YAML，校验生成器白名单、版本和参数约束。
3. 使用规格指纹查找正式图元库或 `generated/component_library` 缓存；未命中时先保存 YAML，再由白名单 OpenCascade 生成器物化 B-Rep STEP。
4. 同一 B-Rep 输出 STEP、Three.js 3D 网格和 SVG 专利附图。

## 启动

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
npm install
cp .env.example .env
# 将 MOONSHOT_API_KEY 写入 .env（本机已配置时无需重复设置）
# 默认启动 5 个相互隔离的 CAD worker，支持至少五个生成请求并行执行
./.venv/bin/python -m app.server
```

可按 CPU 和内存继续提高并发数，例如 `CAD_WORKERS=8 ./.venv/bin/python -m app.server`。
每个 worker 同时只运行一个 OpenCascade 内核任务，避免线程并发导致几何损坏；
不同 worker 可并行服务不同用户或浏览器窗口。建议每个 worker 至少预留 1.5 GB 内存。
齿轮和长丝杠属于高内存任务，默认最多 2 路并行，可通过 `HEAVY_CAD_SLOTS` 调整；
普通模型仍按 `CAD_WORKERS` 的 5 路或更高容量并行。

打开 <http://127.0.0.1:8000>。

开发机上的 systemd、Nginx、HTTPS、更新和故障排查步骤见
[DEPLOYMENT.md](DEPLOYMENT.md)。

## 测试

```bash
./.venv/bin/pytest -q
```

API Key 只从环境变量读取，不会发送给浏览器，也不应提交到仓库。

## STEP / ComponentSpec YAML

`component_library` 是正式图元库，每个图元目录包含 `component.yaml` 和
`reference.step`。现在支持两种几何模式：

- `reference_brep` / `reference_step`：用于外部导入的固定规格件。YAML 记录元数据、坐标系、端口、实测拓扑和校验和，原始 STEP 是几何真值。
- `parametric_brep` / `parametric`：用于 Prompt 生成件。YAML 是参数和生成器版本的事实源，`YAML → STEP` 会重新调用白名单生成器，不是复制旧 STEP。

Prompt 生成的规格和物化 STEP 保存在 `generated/component_library/<spec-id>/`，
该目录不入 Git；审核后可将整个图元目录提升到正式 `component_library`。

```bash
# 任意 STEP 按正式图元库结构建立 YAML + reference STEP 交付对
mkdir -p component_library/my-component
./.venv/bin/python scripts/component_cli.py step-to-yaml \
  input.step component_library/my-component/component.yaml \
  --reference-name reference.step \
  --id my-component --name "我的图元" --type shaft

# YAML 恢复 STEP，并校验 SHA-256
./.venv/bin/python scripts/component_cli.py yaml-to-step \
  component_library/deep-groove-ball-bau6201z/component.yaml /tmp/bearing.step

# 查看包围盒、体积和拓扑
./.venv/bin/python scripts/component_cli.py inspect /tmp/bearing.step

# 校验规范/引用文件，以及执行 OpenCascade 重导出一致性检查
./.venv/bin/python scripts/component_cli.py validate component.yaml
./.venv/bin/python scripts/component_cli.py roundtrip component.yaml --output checked.step

# 已知图元的 STEP 重新建档时关联权威 YAML，保留参数、约束、预设和端口
./.venv/bin/python scripts/component_cli.py step-to-yaml output.step linked.yaml \
  --no-copy-reference --source-spec component_library/<id>/component.yaml
```

服务端同时提供：

- `POST /api/convert/step-to-yaml?filename=part.step`：请求体为 STEP 二进制，返回 YAML 与 reference STEP 下载地址。
- `POST /api/convert/yaml-to-step`：传入 `{"spec_path":"component_library/<id>/component.yaml","reexport":true}` 生成 STEP。
- `GET /api/component-spec/validate?spec_path=component_library/<id>/component.yaml`：校验 YAML、端口、引用文件及校验和。
- `GET /api/components/<id>/yaml`：下载正式图元或 Prompt 生成图元的 ComponentSpec YAML。

端口装配使用 JSON 清单。第一项固定，后续项的 `port` 会与 `target` 指定组件的
`mate_to` 端口原点重合、轴向相反、up 方向对齐：

```json
{"components": [
  {"spec": "component_library/stepped-shaft-mcm01-d30-l70-e45-f45-a20-b20-g18-v18-p12-q12/component.yaml"},
  {"spec": "component_library/deep-groove-ball-bau6201z/component.yaml", "port": "end_a", "target": 0, "mate_to": "end_b"}
]}
```

```bash
./.venv/bin/python scripts/component_cli.py assemble assembly.json assembly.step
```
