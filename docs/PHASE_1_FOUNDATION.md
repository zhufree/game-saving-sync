# 阶段一：项目基础与配置迁移

**目标**: 把项目基础从旧的 DST/Syncthing 同步工具迁移为 P2P 游戏存档传输工具。
**优先级**: P0

## 当前已有基础

- Python 项目结构。
- `AppConfig` 配置持久化。
- Loguru 日志。
- 路径验证、进程检测、二维码、通知等工具函数。
- pytest 测试目录。

## 本阶段任务

### 1.1 项目命名和元数据

- [x] `pyproject.toml` 项目名改为 `game-save-transfer`。
- [x] README 改为新产品定位。
- [x] 入口日志改为 Game Save Transfer。
- [ ] 后续打包图标和窗口标题统一改名。

### 1.2 配置模型迁移

- [x] 新增 `steam_root`。
- [x] 新增 `steam_libraries`。
- [x] 新增 `snapshot_dir`。
- [x] 新增 `known_games`。
- [x] 新增 `transfer_history`。
- [x] 支持从旧字段 `dst_save_path`、`backup_dir` 迁移。
- [x] 旧 Syncthing 字段不再写入新配置。

### 1.3 工具函数调整

- [x] 新增 Steam 路径检测基础函数。
- [x] 保留 DST 路径检测作为首个游戏规则的辅助能力。
- [x] 保留二维码能力，用于后续配对密钥分享。
- [x] 新增 Steam Library 解析工具。
- [ ] 新增文件哈希和目录清单工具。
- [ ] 新增安全写入前的路径风险检查。

### 1.4 测试调整

- [x] 配置测试改为新模型。
- [x] 增加旧配置迁移测试。
- [x] 增加 Steam 路径检测测试。
- [x] 增加 Steam Library 解析测试。
- [ ] 增加存档发现规则测试。
- [ ] 增加传输元数据测试。

## 验收标准

- [x] 项目文档说明新方向。
- [x] 配置文件不再输出旧同步字段。
- [x] 旧配置可以被读取并迁移。
- [x] Python 文件通过语法编译检查。
- [ ] 本地 Python/pytest 环境配置完成后，所有测试通过。

## 下一阶段

完成后进入 **阶段二：P2P 配对与传输**，同时并行推进 Steam 游戏库与存档发现能力。
