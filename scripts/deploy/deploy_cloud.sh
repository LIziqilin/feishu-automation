#!/usr/bin/env bash
# deploy_cloud.sh — 云服务器一键部署 webapi（Linux，root/普通用户均可）
# 用法：把整个项目 scp 到服务器 /opt/feishu-automation 后，在 scripts/ 下执行：
#   bash deploy/deploy_cloud.sh
set -e
APP=/opt/feishu-automation
cd "$APP/scripts"

echo "== 1. 写入环境密钥（如未设置）=="
grep -q WEBAPI_TOKEN webapi_secrets.env 2>/dev/null || \
  echo "WEBAPI_TOKEN=请改成你的强口令" > webapi_secrets.env

echo "== 2. 安装依赖（标准库零依赖，仅需python3）=="
command -v python3 || (apt-get update && apt-get install -y python3)

echo "== 3. 注册 systemd 服务 =="
sed "s#/opt/feishu-automation#$APP#g" deploy/feishu-webapi.service > /etc/systemd/system/feishu-webapi.service
systemctl daemon-reload
systemctl enable --now feishu-webapi

echo "== 4. 验证 =="
sleep 2
curl -s http://127.0.0.1:8765/health && echo ""
echo "✅ 部署完成。记得在云厂商安全组放行 8765，并把 BIND_HOST=0.0.0.0 的服务放在 HTTPS/Nginx 反代后。"
