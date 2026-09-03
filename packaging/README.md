# MediaVault Debian 包

## 安装

```bash
sudo apt update
sudo apt install ./mediavault_1.0.0_all.deb
```

浏览器打开 `http://服务器IP/` 或 `http://服务器IP:8096/`
第一个注册的账号自动成为管理员。

## 卸载（保留媒体库数据库）

```bash
sudo apt remove mediavault
```

## 彻底删除（程序 + 配置 + 数据库）

```bash
sudo apt purge mediavault
```

媒体文件本身不会删（只删 `/var/lib/mediavault` 里本包装的数据和库记录）。你自己磁盘上的电影目录不会被动。

## 路径

| 用途 | 路径 |
|------|------|
| 程序 | `/opt/mediavault` |
| 数据库/默认媒体目录 | `/var/lib/mediavault` |
| 配置 | `/etc/mediavault/mediavault.env` |
| 服务 | `systemctl status mediavault` |

重新打包：先 `npm run build` 前端，再 `python packaging/build_deb.py`
