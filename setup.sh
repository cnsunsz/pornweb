#!/bin/bash
# MediaVault 一键部署脚本（在 VPS 上运行）
# 用法：bash setup.sh

set -e

echo "=== MediaVault 部署 ==="

# 1. 安装依赖
echo "[1/6] 安装 Python 依赖..."
apt update -y
apt install -y python3.14-venv

# 2. 创建 venv 并安装 Python 包
echo "[2/6] 创建虚拟环境..."
python3 -m venv /www/mediavault/backend/venv
source /www/mediavault/backend/venv/bin/activate
pip install --upgrade pip
pip install -r /www/mediavault/backend/requirements.txt
pip install greenlet

# 3. 创建媒体目录
echo "[3/6] 创建媒体目录..."
mkdir -p /www/mediavault/media

# 4. 配置 systemd
echo "[4/6] 配置系统服务..."
cp /www/mediavault/backend/mediavault.service /etc/systemd/system/ 2>/dev/null || true
systemctl daemon-reload
systemctl enable mediavault
systemctl restart mediavault
sleep 3

# 验证后端
if curl -s --max-time 3 http://127.0.0.1:8099/api/health | grep -q "ok"; then
    echo "  ✅ 后端启动成功"
else
    echo "  ❌ 后端启动失败，检查日志：journalctl -u mediavault -n 20"
    exit 1
fi

# 5. 配置 Nginx
echo "[5/6] 配置 Nginx..."
cp /www/mediavault/backend/mediavault.conf /www/server/panel/vhost/nginx/mediavault.conf 2>/dev/null || \
cp /www/mediavault/mediavault.conf /www/server/panel/vhost/nginx/mediavault.conf 2>/dev/null || true
nginx -t && nginx -s reload

echo "[6/6] 部署完成！"
echo ""
echo "访问地址: http://你的服务器IP/"
echo "媒体目录: /www/mediavault/media/"
echo "查看日志: journalctl -u mediavault -f"
echo ""
echo "第一个注册的用户自动成为管理员。"
