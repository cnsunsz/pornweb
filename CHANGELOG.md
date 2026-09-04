# Changelog

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
