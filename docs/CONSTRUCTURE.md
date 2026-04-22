# Game Save Transfer 开发规格文档

**项目名称**: Game Save Transfer
**当前版本**: v0.2 规划版
**最后更新**: 2026-04-22
**目标**: 做一个小规模、点对点的游戏存档传输工具。两个用户通过配对密码建立 P2P 连接，把发送方选择的存档传到接收方相同游戏的对应存档位置。
**目标用户**: 想把单机/联机游戏存档发给朋友、换电脑、临时接管游戏进度的普通玩家。
**平台**: 首要支持 Windows 10/11，后续可扩展 macOS/Linux。

## 1. 产品方向

本项目不再是“持续同步工具”，也不再依赖 Syncthing 作为核心方案。新的核心体验是：

1. 用户配置自己的 Steam 文件夹。
2. 程序扫描 Steam 游戏和常见存档位置。
3. 发送方选择一个游戏存档，生成一次性配对密钥。
4. 接收方输入密钥完成 P2P 配对。
5. 程序把存档写入接收端同一游戏对应的存档目录。
6. 写入前自动创建安全快照，避免覆盖事故。

## 2. 非目标

- 不做多人实时协作编辑同一份存档。
- 不做云同步盘或中心化账号系统。
- 不把 Syncthing 作为用户必须安装的外部依赖。
- 不在游戏运行中强制覆盖存档。
- MVP 不追求支持所有游戏，先建立可扩展规则体系。

## 3. MVP 功能

### 3.1 Steam 配置

- 支持用户选择 Steam 安装目录。
- 自动解析 Steam Library 目录。
- 识别已安装游戏的 appid、名称、安装路径。
- 存储用户确认过的 Steam 库配置。

### 3.2 存档发现

- 提供可扩展的游戏存档规则模型。
- 支持以下常见位置：
  - `%USERPROFILE%\Documents`
  - `%APPDATA%`
  - `%LOCALAPPDATA%`
  - `%USERPROFILE%\Saved Games`
  - Steam userdata: `<Steam>\userdata\<steam_user_id>\<appid>`
  - 游戏安装目录下的 `save`、`saves`、`Saved` 等目录
- DST 可作为首个内置游戏规则模板。
- 用户可以手动选择或修正存档路径。

### 3.3 P2P 配对

- 发送方生成一次性配对密钥。
- 接收方输入密钥后建立连接。
- 配对密钥应包含或可解析出会话 ID、临时公钥、连接候选信息、过期时间。
- 密钥默认短期有效，过期后需要重新生成。
- 后续可以增加二维码展示，但文字密钥是 MVP 必需能力。

### 3.4 存档传输

- 发送端打包所选存档目录或文件。
- 传输元数据包含游戏标识、源存档相对路径、文件清单、大小、校验和。
- 接收端根据本地规则计算目标路径。
- 写入前展示目标路径和覆盖风险。
- 传输完成后做校验并记录历史。

### 3.5 安全快照

- 接收端发现目标路径已有文件时，默认先创建快照。
- 快照用于恢复被覆盖前的状态。
- 快照功能是接收保护，不再作为主功能“备份管理系统”。

### 3.6 GUI

- GUI 使用 PySide6 + `qfluentwidgets`。
- pip 依赖使用 `PySide6-Fluent-Widgets`，代码导入包名是 `qfluentwidgets`。
- 主导航建议：
  - 首页: 当前设备、Steam 配置状态、最近传输。
  - 发送存档: 选择游戏 -> 选择存档 -> 生成密钥 -> 等待接收。
  - 接收存档: 输入密钥 -> 预检目标路径 -> 接收并写入。
  - 游戏库: 查看扫描到的游戏和存档规则。
  - 设置: Steam 路径、快照目录、网络策略、语言。

## 4. 架构建议

```text
src/
  main.py
  config.py
  steam_library.py       # Steam 路径、libraryfolders.vdf、已安装游戏解析
  save_discovery.py      # 游戏存档规则与扫描
  transfer_session.py    # 配对密钥、会话状态、传输元数据
  p2p_transport.py       # P2P 连接与文件传输抽象
  snapshot_manager.py    # 接收前安全快照与恢复
  utils.py
  ui/
    main_window.py
    send_page.py
    receive_page.py
    library_page.py
    settings_page.py
```

## 5. 配置模型建议

```json
{
  "steam_root": "C:\\Program Files (x86)\\Steam",
  "steam_libraries": [],
  "snapshot_dir": "./snapshots",
  "known_games": [],
  "transfer_history": [],
  "first_run": false,
  "language": "zh_CN"
}
```

旧字段迁移：

| 旧字段 | 新字段/处理方式 |
| --- | --- |
| `dst_save_path` | 迁移为游戏规则发现结果，不再作为全局唯一存档路径 |
| `syncthing_path` | 移除 |
| `syncthing_api_key` | 移除 |
| `syncthing_api_url` | 移除 |
| `backup_dir` | 改为 `snapshot_dir` |
| `sync_groups` | 改为 `transfer_history` 或 `saved_peers` |

## 6. P2P 技术路线待决策

可选路线：

1. **libp2p / WebRTC 数据通道**: 更接近真实 P2P，适合 NAT 穿透，但 Python 生态和打包复杂度需要验证。
2. **中继辅助的临时传输**: 体验更稳定，但需要服务端，不符合纯 P2P 初衷。
3. **局域网优先 + 手动端口/UPnP**: 实现快，但公网可用性弱。

MVP 建议先做网络层抽象和本地/局域网传输原型，再决定公网 P2P 方案，避免 GUI 和业务逻辑被某个传输库锁死。

## 7. 风险

- NAT 穿透是最大技术风险，必须早做可行性验证。
- 游戏存档路径差异很大，需要规则体系和用户确认机制兜底。
- 覆盖存档风险高，接收前快照和游戏进程检测必须是 P0。
- `PySide6-Fluent-Widgets` 是 GPLv3/商业双许可证，发布方式要提前确认。
