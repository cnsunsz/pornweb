# PornWeb

自托管媒体库。扫本地影片和 NFO 资料包，在浏览器里浏览、搜刮进度可见、在线播放。

后端 FastAPI + SQLite，前端 Vue 3。界面默认深色，支持简体 / 繁体 / English / 日本語。第一个注册的账号自动成为管理员。

> 仓库里部分路径、服务名仍叫 `mediavault`（历史名称），界面品牌是 **PornWeb**。

## 功能

- **媒体库**：添加一个或多个本地目录；支持电影、剧集；识别海报 / 背景图 / NFO
- **增量扫库**：扫描在后台线程跑，边扫边写入数据库，设置页轮询进度，文件很多时也不会把页面卡住
- **在线播放**：Range 流式传输，支持继续观看、分段、画中画
- **用户**：注册 / 登录 / JWT；管理员可管用户和服务器设置
- **服务器设置**：后端端口、监听地址（`127.0.0.1` / `0.0.0.0`）、对外 HTTP 端口；保存监听地址或后端端口会重启服务
- **多语言**：`zh-CN`、`zh-TW`、`en`、`ja`

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3、FastAPI、Uvicorn、SQLAlchemy、SQLite（WAL） |
| 前端 | Vue 3、Vite、Pinia、Vue Router、Element Plus、vue-i18n |
| 部署 | systemd、Nginx 反代；也可打 Debian 包 |

## 仓库结构

```
backend/          FastAPI 应用、扫库、NFO 解析
frontend/         Vue 源码（开发）和构建产物目录
deploy/           Nginx / systemd 示例
packaging/        Debian 打包
setup.sh          VPS 一键脚本（需先把文件放到 /www/mediavault）
启动本地测试.bat   Windows 一键起前后端
停止本地测试.bat
DEPLOY.md         更细的部署步骤
```

不要提交 `.env`、`venv/`、`node_modules/`、媒体文件和 SQLite 数据库。

## 本地运行

### Windows

1. 复制 `backend/.env.example` 为 `backend/.env`，把 `SECRET_KEY` 改成随机字符串。
2. 双击 `启动本地测试.bat`。
3. 浏览器打开 http://127.0.0.1:5173 。

| 地址 | 说明 |
| --- | --- |
| http://127.0.0.1:5173 | 前端（Vite 开发服务器） |
| http://127.0.0.1:8099 | 后端 API / 播放流 |
| http://127.0.0.1:8099/docs | OpenAPI 文档 |

媒体文件默认放在 `backend/media/`。在控制台添加媒体库并扫描。双击 `停止本地测试.bat` 结束进程。

### Linux / macOS

后端在 `backend/` 建虚拟环境并安装 `requirements.txt`，再运行 `run.py`（默认端口 8099）。前端在 `frontend/` 安装依赖后启动 Vite 开发服务（默认 5173，已把 `/api` 代理到后端）。记得先把 `backend/.env.example` 复制为 `backend/.env` 并改掉 `SECRET_KEY`。

## 生产部署（Ubuntu）

1. 后端放到 `/www/mediavault/backend/`；前端先构建，把产物放到 `/www/mediavault/frontend/`。
2. 在服务器上执行仓库里的 `setup.sh`，或按 `DEPLOY.md` 配置 systemd 与 Nginx。
3. 编辑 `/www/mediavault/backend/.env`（至少改 `SECRET_KEY`、`MEDIA_ROOT`）。
4. Nginx 对外端口看 `.env` 里的 `PUBLIC_PORT`（示例默认 `5588`）。站点根目录指向前端静态文件，`/api/` 反代到本机 `8099`。

示例配置在 `deploy/nginx_mediavault.conf`。`index.html` 不要缓存（模板已加 `Cache-Control: no-store`），带 hash 的 js/css 可以长期缓存。

若用宝塔，实际 vhost 文件名可能是 `html_mediavault.conf` 而不是 `mediavault.conf`；设置页会按文件名自动查找。

Debian 包说明见 `packaging/README.md`。

### 国内云端口

部分国内云（例如 AWS 中国）在未完成 ICP 备案和白名单前会拦截 **80 / 443 / 8080**。此时请把 Nginx 对外端口改成未被拦截的端口（例如 `10086`），并在安全组和 `.env` 的 `PUBLIC_PORT` 里保持一致。不要误以为改成 80 就能通。

## 扫库说明

- 请求立即返回，扫描在后台进行。
- 每发现一部作品就写入数据库，刷新列表能看到数量增加。
- 设置页的媒体库卡片会显示进度（已处理 / 已发现 / 状态文案）。
- 跳过 `node_modules`、`.git`、`venv`、回收站等目录，以及 sample 片。
- 海报优先匹配 `poster` / `folder` / `cover` 以及与片名同 stem 的图片；元数据读 NFO。

文件特别多时，请用控制台的「扫描」并等进度走完，不要反复强制刷新整页当唯一反馈。

## 环境变量

写在 `backend/.env`（或 `/etc/mediavault/mediavault.env`）：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `APP_NAME` | `PornWeb` | 显示名称 |
| `SECRET_KEY` | （示例值） | JWT 密钥，生产环境必须改掉 |
| `DATABASE_URL` | SQLite 本地库 | 数据库连接 |
| `MEDIA_ROOT` | 视部署而定 | 媒体根目录 |
| `HTTP_PORT` | `8099` | 后端监听端口 |
| `BIND_HOST` | `127.0.0.1` | `0.0.0.0` 允许局域网或经反代访问 |
| `PUBLIC_PORT` | `5588` | Nginx 对外端口 |
| `CORS_ORIGINS` | `["*"]` | 跨域来源 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | 登录有效期（分钟） |

## 前端构建注意

打包时会把 **Element Plus 拆成独立 chunk**，避免异步页面去引用入口 bundle。不要给入口 JS 加 `?v=` 这类查询串做缓存刷新，否则可能加载两份 Vue 运行时，控制台黑屏。需要刷新时改文件名 hash，或只禁止缓存 `index.html`。

## 许可

[MIT](LICENSE)
