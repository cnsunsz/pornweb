# Changelog

## [v2.1.5] - 2026-09-07

### 新增
- 演员在线头像：`GET /api/actors/photo?name=…`（TMDB person，同源代理）

### 修复
- 演员列表不再用作品海报冒充头像；无在线头像时 `poster_url` 为空，客户端须留空
- 强制刮削时不再用空 `cast_list` 覆盖已有演员表


## [v2.1.4] - 2026-09-07

### 修复
- 海报墙空白：列表/详情的 `poster_url`/`fanart_url` 统一返回同源 `/api/media/poster/{id}`（不再把豆瓣/TMDB 外链直接塞给浏览器，避免防盗链裂图）
- `/api/media/poster|fanart/{id}` 对远程图改为服务端代抓回传，不再 307 跳转


## [v2.1.3] - 2026-09-07

### 修复
- TMDB：国内 AWS 等环境无法访问 `api.themoviedb.org`，改为优先使用 `api.tmdb.org`，并保留官方域名回退
- 豆瓣：从文件夹路径提取中文片名（如 `天才游戏[...].Game.of.Identity...`）优先检索；英文名无结果时回退英文并按年份择优


## v2.1.1
### 改进
- **元数据设置对齐 Emby / Jellyfin**：控制台「元数据」改为「优先本地 NFO」「启用互联网下载器」+ 按源启用的下载器列表（TMDB / 豆瓣 / JavDB），TMDB API Key 放在源详情行；语言偏好、保存图片到媒体夹（占位）、高级 Cookie/代理/顺序折叠
- 文案澄清：识别/刷新与扫库共用这些源；**只补元数据与海报 URL，不替换本地视频文件**；详情按钮改为「识别/刷新元数据」
- **仅管理员**可读取/修改刮削相关服务器设置（`GET/PUT /api/settings/`）；`POST /api/media/{id}/scrape` 改为管理员；非管理员设置页不显示元数据区块（本就无服务器页）
- 新增配置：`SCRAPER_PREFER_LOCAL`、`SCRAPER_INTERNET_ENABLED`、`SCRAPER_METADATA_LANGUAGE`、`SCRAPER_SAVE_ARTWORK`（热更新）；TMDB 请求使用配置的语言

### 说明
- Android **不实现**刮削配置与触发（云端 Web / 管理员操作）
- 各下载器仍 soft-fail；打包避免 element-plus 单独 `manualChunks`



## v2.1.0
### 新增
- **可选云端刮削**：豆瓣（Douban）、TMDB、JavDB。本地 NFO 优先；元数据不足时在扫库 `scrape` 阶段或单片刷新时补全
- 服务器设置页「云端刮削」：开关、TMDB API Key、优先级顺序、可选代理；写入 `.env` 并可热更新
- 单片接口 `POST /api/media/{id}/scrape`（可选 `{ providers?, force? }`），供 Web / Android 调用
- 详情页管理员「刮削元数据」按钮；扫库进度新增 `scrape` 阶段文案（简中 / 繁中 / English / 日本語）

### 说明
- TMDB 启用时必须配置 `TMDB_API_KEY`；豆瓣 / JavDB 为 best-effort，超时或风控时软跳过，不阻塞整库扫描
- 可选 `SCRAPER_DOUBAN_COOKIE` / `SCRAPER_JAVDB_COOKIE` / `SCRAPER_PROXY`（高级，默认空）
- 优先级默认 `SCRAPER_ORDER=nfo,tmdb,douban,javdb`；合并策略为补空字段（`force=true` 可覆盖）
- 打包仍避免 element-plus 单独 `manualChunks`；入口不加 `?v=`


## v2.0.1
### 改进
- **品牌字标重设计**：去掉 Pornhub 式「白字 + 橙底黑字 Web」克隆；改为独立 PornWeb 标识（圆角媒体框 + 播放三角 + 网络节点图标，字标 Web 用强调色下划线）
- 顶栏 Logo、登录/注册页、favicon 同步新标识
- 登录/注册页增加克制动效：卡片淡入上滑、背景柔光脉冲、Logo 轻微呼吸（尊重 `prefers-reduced-motion`）
- 首页保持 v2.0.0 Tube 密集封面墙布局不变

### 说明
- 打包仍避免 element-plus 单独 `manualChunks`；入口脚本不加 `?v=` 缓存破坏（依赖 Nginx 对 `index.html` 的 no-store）

## v2.0.0
### 新增
- 公共浏览 UI 全面改为成人 Tube 站视觉（Pornhub / 法国啄木鸟风格）：炭黑底、橙金强调色、密集封面墙
- 顶栏：PornWeb 字标、搜索框、分类/演员/控制台导航；登录注册页同品牌深色样式
- 封面卡：时长角标、悬停播放层、评分角标、双行标题与类型元信息
- 首页：分类/媒体库 chips、「最新/推荐」密集网格；顶栏搜索联动结果
- 详情页：大图英雄区、演员芯片、下方相关推荐封面墙

### 改进
- 控制台/设置侧栏与按钮强调色对齐 Tube 橙金主题（仍用 Element Plus，功能不变）
- 播放器进度条与倍速角标改为橙金强调色
- 首页默认每页 48 条以适配密集封面墙；布局最大宽度放宽至约 1680px
- 多语言（简中 / 繁中 / English / 日本語）补充搜索占位、全部、相关推荐等文案


## v1.3.0
### 新增
- Emby / Jellyfin 风格**演员表**：从 NFO `cast_list` 聚合全库演员，导航「演员」页展示姓名、作品数与海报缩略图；支持搜索过滤
- 点击演员进入其作品列表（卡片样式同首页）；详情页演员名改为可点击芯片，跳转对应演员页
- 后端 API（Web / Android 共用，Bearer JWT）：
  - `GET /api/actors` → `{ items: [{ name, count, poster_url }], total }`（`poster_url` 如 `/api/media/poster/{id}`，可空）
  - `GET /api/actors/{name}/media` → 与 `/api/media/list` 相同的 `MediaListResponse`（**推荐**；CJK 姓名须 URL 编码）
  - 兼容：`GET /api/actors/{name}`、`GET /api/actors/by-name?name=`
  - 稳健解析 JSON / 分隔符，过滤空占位，保留「佚名」

## v1.2.0
### 新增
- Emby / Jellyfin 风格**自动扫库**：启动时监视各媒体库目录（watchdog），文件系统事件防抖后触发增量扫描；rclone/FUSE 无可靠 inotify 时依赖**定时全库扫描**（默认 15 分钟，可配置）
- 服务器设置页增加「自动扫库」开关与扫描间隔；写入 `.env`（`AUTO_SCAN_ENABLED` / `AUTO_SCAN_INTERVAL_MINUTES`），运行时可热更新
- 扫库进度新增 `metadata` 阶段：UI 显示「正在读取元数据：标题 (3/120)」等文案（简中 / 繁中 / English / 日本語）

### 修复·改进
- NFO 解析改为**一次读入字节**（上限约 2MB）后在内存中尝试多编码，避免 rclone 上反复 `open`；相对海报/fanart 路径直接拼接，**不再**对 FUSE 路径做 `Path.exists()` 阻塞检查；优先使用 `defusedxml`
- 扫库两阶段：先快速入库标题（discover），再元数据 enrichment（metadata）；进度回调节流（约 0.5s），减轻扫库时 DB 写入放大卡顿
- 已有条目且 NFO 未变时可跳过重新解析（新增可选列 `nfo_mtime`）；已有 `file_size > 0` 的条目跳过昂贵的整片 `stat`；`stat` 失败不中断扫描
- 依赖增加 `watchdog`

## v1.1.1
### 修复
- 去掉错误的 Element Plus `manualChunks`（仅拆出 element-plus），修复控制台黑屏（`t is not a function`，Vue 无法挂载）
- 说明：v1.1.0 功能（扫库进度条、播放设置、PotPlayer 风格快捷键等）仍在；本次仅修正打包分块导致的运行时崩溃

## v1.1.0
### 新增
- Emby / Jellyfin 风格扫库进度条：媒体库管理页按库显示进度、阶段文案与 found/added/updated/removed/processed 计数；`found > 0` 时按 `processed/found` 计算百分比，否则扫描中显示条纹不确定进度；顶部可粘性精简进度条；扫描按钮在对应库扫描时保持 loading/禁用；仍为后台非阻塞扫描
- 播放设置（对齐 Android v1.0.6 `PlaybackSettingsScreen` / `PlayerPrefs`）：默认倍速、长按倍速、左右跳过秒数、横向滑动灵敏度；开关含双击快进/快退、左侧长按倒退、打开时自动全屏、有进度时自动续播
- 设置控制台新增「播放设置」页；播放器顶栏齿轮可跳转
- 偏好持久化到 `localStorage` 键 `pw_player`（与 Android SharedPreferences 名一致）
- PotPlayer 风格快捷键：← → 按设定秒数跳转，↑ ↓ 音量，空格播放/暂停（长按临时加速），F 全屏，M 静音；输入框 / Element Plus 弹层聚焦时忽略

### 修复·改进
- 跳过按钮秒数随「左右跳过秒数」设置变化，不再写死 10 秒
- 打开播放器时应用默认倍速；可按设置决定是否自动续播 / 自动全屏
- 视频区域支持双击左右半屏跳转、长按左右半区倒退/加速、横向拖动按灵敏度 seek
- 补充简体 / 繁体 / English / 日本語文案

## v1.0.0
### 新增
- 首个公开 Web 版：媒体库扫库、详情、在线播放、用户与服务器设置、多语言
