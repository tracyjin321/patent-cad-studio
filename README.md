# 专图灵境

面向机械单零件的专利附图/CAD 方案生成工作台。支持轴承、法兰、阀门、轴系、齿轮、丝杠、联轴器、密封件。

生成链路由两层组成：

1. Moonshot 从自然语言中提取结构参数（未配置或调用失败时自动使用本地解析）。
2. OpenCascade 参数化几何引擎生成真实 B-Rep STEP，Three.js/WebGL 使用 PBR 材质、灯光和阴影展示交互式 3D 模型，同时输出可编辑 SVG 技术附图。

## 启动

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
npm install
cp .env.example .env
# 将 MOONSHOT_API_KEY 写入 .env（本机已配置时无需重复设置）
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

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
`reference.step`。导入模型采用
`reference_brep` 表示：参数、坐标系、装配端口和实测拓扑写入 YAML，原始 STEP 作为
几何真值，因此未变换的 YAML → STEP 是字节级无损的。

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
```

服务端同时提供：

- `POST /api/convert/step-to-yaml?filename=part.step`：请求体为 STEP 二进制，返回 YAML 与 reference STEP 下载地址。
- `POST /api/convert/yaml-to-step`：传入 `{"spec_path":"component_library/<id>/component.yaml","reexport":true}` 生成 STEP。
- `GET /api/component-spec/validate?spec_path=component_library/<id>/component.yaml`：校验 YAML、端口、引用文件及校验和。

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
