#!/bin/bash
set -e

echo "=========================================="
echo "  MediaVault 安装脚本"
echo "  类 Jellyfin 自托管媒体平台"
echo "=========================================="
echo ""

# Check root
if [ "$(id -u)" -ne 0 ]; then
    echo "请用 root 运行此脚本: sudo bash install.sh"
    exit 1
fi

# Detect OS
if [ -f /etc/debian_version ]; then
    PKG="apt"
elif [ -f /etc/redhat-release ]; then
    PKG="yum"
else
    echo "不支持的系统，仅支持 Debian/Ubuntu/CentOS"
    exit 1
fi

INSTALL_DIR="/www/mediavault"
MEDIA_DIR="/www/mediavault/media"

echo "[1/6] 安装系统依赖..."
if [ "$PKG" = "apt" ]; then
    apt update -y
    apt install -y python3 python3-pip python3-venv nginx curl
else
    yum install -y python3 python3-pip nginx curl
fi

echo "[2/6] 创建目录..."
mkdir -p "$INSTALL_DIR"/{backend,data}
mkdir -p "$MEDIA_DIR"

echo "[3/6] 部署后端..."
cp -r backend/* "$INSTALL_DIR/backend/"
cd "$INSTALL_DIR/backend"

if [ ! -f .env ]; then
    SK=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    cat > .env << EOF
SECRET_KEY=$SK
MEDIA_ROOT=$MEDIA_DIR
DATABASE_URL=sqlite+aiosqlite:///./data/mediavault.db
CORS_ORIGINS=["*"]
EOF
    echo "  已生成 .env"
fi

# Create venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install greenlet pydantic-settings

echo "[4/6] 配置系统服务..."
cat > /etc/systemd/system/mediavault.service << 'SVCEOF'
[Unit]
Description=MediaVault - Self-hosted Media Server
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
SVCEOF

systemctl daemon-reload
systemctl enable mediavault
systemctl start mediavault
sleep 3

# Verify backend
if curl -s --max-time 5 http://127.0.0.1:8099/api/health | grep -q "ok"; then
    echo "  ✅ 后端启动成功"
else
    echo "  ❌ 后端启动失败，运行 journalctl -u mediavault -n 20 查看日志"
    exit 1
fi

echo "[5/6] 配置 Nginx..."
# Deploy frontend
mkdir -p /www/mediavault/frontend
cp -r frontend/* /www/mediavault/frontend/

cat > /etc/nginx/sites-available/mediavault << 'NGXEOF'
server {
    listen 5588;
    server_name _;
    index index.html;
    root /www/mediavault/frontend;

    client_max_body_size 100m;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8099;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;
        proxy_no_cache $http_range;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
NGXEOF

ln -sf /etc/nginx/sites-available/mediavault /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default 2>/dev/null
nginx -t && systemctl restart nginx

echo "[6/6] 安装完成！"
echo ""
echo "=========================================="
echo "  ✅ MediaVault 安装成功！"
echo ""
echo "  访问地址: http://$(hostname -I | awk '{print $1}')/"
echo "  媒体目录: $MEDIA_DIR"
echo ""
echo "  使用说明:"
echo "  1. 打开浏览器访问上述地址"
echo "  2. 注册账号（第一个自动为管理员）"
echo "  3. 管理页面添加媒体库路径"
echo "  4. 将视频和NFO文件放到媒体目录"
echo "  5. 扫描即可看到媒体"
echo ""
echo "  常用命令:"
echo "  查看状态: systemctl status mediavault"
echo "  查看日志: journalctl -u mediavault -f"
echo "  重启服务: systemctl restart mediavault"
echo "=========================================="
