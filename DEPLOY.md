# MediaVault 部署指南

## 本地测试

双击 `启动本地测试.bat`，浏览器打开 http://127.0.0.1:5173

- 后端 API: http://127.0.0.1:8099
- API 文档: http://127.0.0.1:8099/docs
- 媒体文件放在 `backend/media/` 目录
- 第一个注册的用户自动成为管理员
- 管理页面可以扫描媒体文件夹

双击 `停止本地测试.bat` 停止所有服务。

---

## VPS 部署（Ubuntu 22.04）

### 1. 上传文件

| 本地路径 | VPS 路径 |
|---------|---------|
| `backend\` | `/www/mediavault/backend/` |
| `frontend\dist\` | `/www/mediavault/frontend/` |

### 2. VPS 一键部署

```bash
apt update && apt install -y python3 python3-pip python3-venv nginx

python3 -m venv /www/mediavault/backend/venv
source /www/mediavault/backend/venv/bin/activate
pip install -r /www/mediavault/backend/requirements.txt
pip install greenlet pydantic-settings

cat > /etc/systemd/system/mediavault.service << 'EOF'
[Unit]
Description=MediaVault Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/www/mediavault/backend
ExecStart=/www/mediavault/backend/venv/bin/python run.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload && systemctl enable mediavault && systemctl start mediavault

cat > /etc/nginx/sites-available/mediavault << 'EOF'
server {
    listen 5588;
    server_name _;
    root /www/mediavault/frontend;
    index index.html;
    client_max_body_size 100m;
    location / { try_files $uri $uri/ /index.html; }
    location /api/ {
        proxy_pass http://127.0.0.1:8099;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Range $http_range;
        proxy_read_timeout 600s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/mediavault /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
```

### 3. 修改 .env

编辑 `/www/mediavault/backend/.env`：
```
MEDIA_ROOT=/www/mediavault/media
```

### 4. 访问

浏览器打开 `http://你的IP/`
