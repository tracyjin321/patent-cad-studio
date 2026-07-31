# 开发机部署教程

本文以 Ubuntu 22.04/24.04、域名或开发机 IP、Nginx、systemd 为例。应用由
FastAPI 提供 API 和静态页面，OpenCascade 负责 STEP 几何生成，Three.js
负责浏览器 3D 渲染。

## 1. 机器要求

- 2 核 CPU、4 GB 内存以上
- Python 3.11 或 3.12
- Node.js 20 或 22
- 可访问 Moonshot API 和 PyPI/npm
- 开放 HTTP 端口 80；需要 HTTPS 时再开放 443

不要使用 Python 3.9。OpenCascade 的预编译 wheel 对 Python 和 CPU
架构有要求，建议优先使用 Python 3.11。

## 2. 安装系统依赖

```bash
sudo apt update
sudo apt install -y git nginx python3 python3-venv python3-pip curl
```

安装 Node.js 22：

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node --version
npm --version
```

## 3. 拉取代码

建议统一安装到 `/opt/patent-cad-studio`：

```bash
sudo mkdir -p /opt/patent-cad-studio
sudo chown "$USER":"$USER" /opt/patent-cad-studio
git clone git@github.com:HenryKamg/patent-cad-studio.git /opt/patent-cad-studio
cd /opt/patent-cad-studio
```

如果开发机没有配置 GitHub SSH Key，可以使用 HTTPS：

```bash
git clone https://github.com/HenryKamg/patent-cad-studio.git /opt/patent-cad-studio
```

## 4. 安装项目依赖

```bash
cd /opt/patent-cad-studio
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
npm ci
```

验证 OpenCascade：

```bash
./.venv/bin/python -c "from OCP.STEPControl import STEPControl_Writer; print('OpenCascade OK')"
```

## 5. 配置 Moonshot

`.env` 不在 Git 中，需要在开发机单独创建：

```bash
cd /opt/patent-cad-studio
cp .env.example .env
chmod 600 .env
nano .env
```

内容如下：

```dotenv
MOONSHOT_API_KEY=替换为你的Moonshot_API_Key
MOONSHOT_MODEL=kimi-k2.6
MOONSHOT_BASE_URL=https://api.moonshot.cn/v1
```

不要把 `.env` 加入 Git，也不要将 Key 写进 systemd、Nginx 或前端文件。

## 6. 首次启动验证

```bash
cd /opt/patent-cad-studio
./.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000
```

另开一个终端检查：

```bash
curl http://127.0.0.1:8000/api/health
```

预期返回：

```json
{"status":"ok"}
```

然后按 `Ctrl+C` 停止临时进程。

## 7. 配置 systemd 常驻服务

创建服务文件：

```bash
sudo nano /etc/systemd/system/patent-cad-studio.service
```

写入以下内容。把 `User` 和 `Group` 改为实际部署用户：

```ini
[Unit]
Description=Patent CAD Studio
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/patent-cad-studio
ExecStart=/opt/patent-cad-studio/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=3
TimeoutStopSec=30
Environment=PYTHONUNBUFFERED=1

# 基础安全限制
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=/opt/patent-cad-studio/generated

[Install]
WantedBy=multi-user.target
```

创建生成目录并启动：

```bash
cd /opt/patent-cad-studio
mkdir -p generated
sudo chown -R ubuntu:ubuntu /opt/patent-cad-studio
sudo systemctl daemon-reload
sudo systemctl enable --now patent-cad-studio
sudo systemctl status patent-cad-studio
```

如果部署用户不是 `ubuntu`，上面的 `chown` 也要替换。

查看日志：

```bash
sudo journalctl -u patent-cad-studio -f
```

## 8. 配置 Nginx

创建站点配置：

```bash
sudo nano /etc/nginx/sites-available/patent-cad-studio
```

使用开发机 IP 时：

```nginx
server {
    listen 80;
    server_name _;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Kimi 参数解析和复杂 STEP 生成可能需要较长时间
        proxy_connect_timeout 15s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/patent-cad-studio \
  /etc/nginx/sites-enabled/patent-cad-studio
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

现在可访问：

```text
http://开发机IP/
```

## 9. 配置 HTTPS（可选）

已有域名并且 DNS 指向开发机时：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d cad.example.com
```

Certbot 会自动修改 Nginx 配置并设置证书续期。

## 10. 部署验证

健康检查：

```bash
curl http://开发机IP/api/health
```

接口生成测试：

```bash
curl -X POST http://开发机IP/api/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "description": "生成模数3、齿数24的直齿圆柱齿轮，中心孔32mm，齿宽28mm。",
    "part_type": "gear",
    "field": "机械结构",
    "use_ai": true
  }'
```

重点检查：

1. 返回的 `parser` 为 `moonshot`。
2. 页面可以切换“3D 预览”“附图预览”“参数文档”。
3. 3D 模型可以旋转和缩放。
4. “下载 STEP”返回 `.step` 文件。
5. Nginx 和浏览器控制台没有 404/500。

## 11. 后续更新

每次发布新代码：

```bash
cd /opt/patent-cad-studio
git pull --ff-only origin main
./.venv/bin/pip install -r requirements.txt
npm ci
./.venv/bin/python -m pytest -q
sudo systemctl restart patent-cad-studio
sudo systemctl status patent-cad-studio
```

推荐先运行测试，测试通过后再重启服务。

## 12. 回滚

查看提交：

```bash
cd /opt/patent-cad-studio
git log --oneline -10
```

临时回滚到某个已知可用提交：

```bash
git checkout <commit_sha>
./.venv/bin/pip install -r requirements.txt
npm ci
sudo systemctl restart patent-cad-studio
```

恢复最新主分支：

```bash
git switch main
git pull --ff-only origin main
sudo systemctl restart patent-cad-studio
```

## 13. 常见故障

### 页面显示 502 Bad Gateway

```bash
sudo systemctl status patent-cad-studio
sudo journalctl -u patent-cad-studio -n 100 --no-pager
curl http://127.0.0.1:8000/api/health
```

通常是 Python 依赖未安装、服务用户错误或端口被占用。

### 生成记录显示“智能解析降级”

日志会显示具体原因：

```bash
sudo journalctl -u patent-cad-studio -f
```

然后检查 `.env`、Moonshot Key、开发机外网以及代理超时。

### OpenCascade 安装失败

确认 Python 版本和 CPU 架构：

```bash
python3 --version
uname -m
```

优先使用 Python 3.11/3.12 的 64 位 Linux 环境，不要从源码编译
OpenCascade。

### STEP 生成后无法下载

```bash
ls -lah /opt/patent-cad-studio/generated
sudo -u ubuntu touch /opt/patent-cad-studio/generated/write-test
```

如果写入失败，修复目录所有权后重启：

```bash
sudo chown -R ubuntu:ubuntu /opt/patent-cad-studio/generated
sudo systemctl restart patent-cad-studio
```

### 查看当前服务版本

```bash
cd /opt/patent-cad-studio
git rev-parse --short HEAD
git status --short
```
