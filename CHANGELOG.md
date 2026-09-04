# Changelog

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
