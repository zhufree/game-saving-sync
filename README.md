# Game Save Transfer

一个小规模、点对点的游戏存档传输工具。它不再定位为持续同步服务，而是帮助两个用户通过配对密码建立 P2P 连接，并把游戏存档安全地传到对方机器上的对应存档位置。

## 当前定位

- **软件形式**: Windows 桌面客户端。
- **连接方式**: 两个用户通过配对密码/密钥建立 P2P 会话。
- **配置方式**: 用户先配置自己的 Steam 文件夹，程序根据常见游戏存档位置自动发现可传输的存档。
- **传输方式**: 发送方选择游戏和存档，生成配对密钥；接收方输入密钥后接收文件。
- **落盘方式**: 接收端根据同一游戏的存档规则写入对应位置，写入前保留本地安全快照。

## MVP 功能

1. **Steam 路径配置**
   - 首次启动引导用户选择 Steam 安装目录或 Steam Library 目录。
   - 自动扫描 `steamapps`、`steamapps/libraryfolders.vdf`，识别已安装游戏。
   - 支持用户手动补充游戏存档目录。

2. **游戏存档发现**
   - 内置常见存档位置规则，例如 `Documents`、`AppData`、Steam userdata、游戏安装目录下的 save/config 目录。
   - 按游戏展示可发送的世界/存档包，让用户确认要发送哪一份存档。
   - DST 会从 `Documents\Klei\DoNotStarveTogether\<用户ID>\Cluster_*` 识别单个世界。
   - 星露谷会从 `%APPDATA%\StardewValley\Saves\<存档名>` 识别单个农场存档。
   - 僵尸毁灭计划会从 `%USERPROFILE%\Zomboid\Saves\<模式>\<存档名>` 识别单个存档。

3. **P2P 配对与传输**
   - 发送方创建传输会话并生成一次性配对密钥。
   - 接收方输入密钥后完成配对。
   - 传输内容包含存档文件和目标路径元数据。
   - 传输完成后展示校验结果。

4. **安全写入**
   - 接收前检测目标路径是否已有存档。
   - 默认创建本地快照，避免覆盖后无法恢复。
   - 检测游戏进程运行时，提示关闭游戏后再写入。

5. **GUI**
   - 使用 PySide6 + `qfluentwidgets`，对应依赖包为 `PySide6-Fluent-Widgets`。
   - 主界面围绕“配置 Steam / 发送存档 / 接收存档 / 传输历史”四个入口设计。

## 当前开发进度

已完成：
- Python 项目基础结构。
- 配置管理基础能力。
- Steam Library 与 appmanifest 基础解析。
- 常见用户目录存档规则配置与扫描基础能力。
- DST `Cluster_*` 世界级存档包扫描。
- qfluentwidgets 简版 GUI。
- LAN/localhost 直连 P2P 传输原型：打包、配对密钥、发送、接收、sha256 校验。
- 公网信令 + 中继兜底原型：填写公网服务器后生成 `GST-...` 远程密钥。
- 服务端版本检查 API：`GET /api/version?current_version=...`。
- 路径检测、进程检测、二维码生成、通知等工具函数。
- 基础单元测试框架。

下一步：
- 扩展更多游戏的内置存档规则。
- 改进发送/接收页面体验。
- 增加客户端端到端加密，避免中继服务器看到明文存档。
- 实现接收前安全快照。

## 公网服务器

服务器配置见 [RELAY_SERVER.md](RELAY_SERVER.md)。

## Windows 打包

打包说明见 [docs/PACKAGING.md](docs/PACKAGING.md)。

快速打包：

```bat
package_app.bat
```

打包产物：

```text
dist\GameSaveTransfer-windows-x64.zip
```

## 快速开始

```bash
setup_dev.bat
```

或手动安装依赖：

```bash
uv sync --group dev
```

运行当前入口：

```bash
uv run python src\main.py
```

## 测试

```bash
uv run pytest
```

## 技术栈

- Python 3.11+
- PySide6
- PySide6-Fluent-Widgets (`from qfluentwidgets import ...`)
- Pydantic
- Loguru
- psutil
- pytest

## 许可证注意

`PySide6-Fluent-Widgets` 使用 GPLv3/商业双许可证。若本项目未来闭源或商业发布，需要购买/确认商业授权；若保持开源，需要确保项目许可证与 GPLv3 兼容。


