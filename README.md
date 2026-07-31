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
