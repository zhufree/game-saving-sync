# 阶段四：qfluentwidgets GUI 实现

**目标**: 使用 PySide6 + `qfluentwidgets` 实现桌面客户端。
**优先级**: P0
**前置依赖**: 配置模型、Steam 扫描、存档发现、传输会话、安全快照基础能力。

## 技术选择

- Qt 绑定: PySide6
- Fluent 组件库: PySide6-Fluent-Widgets
- 代码导入: `from qfluentwidgets import ...`
- 注意: 不要同时安装 PyQt-Fluent-Widgets、PyQt6-Fluent-Widgets、PySide2-Fluent-Widgets 和 PySide6-Fluent-Widgets，因为它们的导入包名都叫 `qfluentwidgets`。

## 主界面结构

建议使用 `FluentWindow` 或等价导航结构：

```text
Game Save Transfer
├─ 首页
├─ 发送存档
├─ 接收存档
├─ 游戏库
├─ 传输历史
└─ 设置
```

## 页面设计

### 4.1 首页

- 显示 Steam 配置状态。
- 显示扫描到的游戏数量。
- 显示最近一次传输结果。
- 提供两个主按钮：发送存档、接收存档。

推荐组件：
- `TitleLabel`
- `CardWidget`
- `PrimaryPushButton`
- `InfoBar`

### 4.2 首次启动向导

流程：

1. 选择 Steam 文件夹。
2. 扫描游戏库。
3. 展示可识别的游戏和存档。
4. 设置快照目录。
5. 完成并进入首页。

### 4.3 发送存档页面

流程：

1. 选择游戏。
2. 选择发现到的存档目录。
3. 预览文件数量和大小。
4. 创建传输会话。
5. 显示配对密钥和二维码。
6. 展示连接状态和发送进度。

### 4.4 接收存档页面

流程：

1. 输入配对密钥。
2. 解析发送方元数据。
3. 匹配本机同一游戏和目标存档路径。
4. 展示覆盖风险。
5. 创建安全快照。
6. 接收并写入。
7. 展示校验结果。

### 4.5 游戏库页面

- 展示已识别 Steam 游戏。
- 展示每个游戏的存档发现结果。
- 支持手动添加/修正存档路径。
- 支持重新扫描。

### 4.6 设置页面

- Steam 根目录。
- Steam Library 列表。
- 快照目录。
- 网络策略。
- 语言。
- 许可证说明。

## UI 状态与错误提示

- 密钥过期: 使用 `InfoBar.warning`。
- 连接失败: 使用 `InfoBar.error`，并给出重试/重新生成密钥入口。
- 游戏正在运行: 使用确认对话框阻止写入。
- 覆盖本地存档: 必须展示目标路径和快照位置。

## 文件结构建议

```text
src/ui/
  app.py
  main_window.py
  pages/
    home_page.py
    send_page.py
    receive_page.py
    library_page.py
    history_page.py
    settings_page.py
  components/
    game_card.py
    save_path_card.py
    transfer_progress_card.py
```

## 任务清单

- [ ] 引入 `PySide6-Fluent-Widgets` 依赖。
- [ ] 创建 `MainWindow` 和导航页面。
- [ ] 实现首次启动向导。
- [ ] 实现发送流程 UI。
- [ ] 实现接收流程 UI。
- [ ] 实现游戏库扫描结果展示。
- [ ] 实现安全快照确认对话框。
- [ ] 实现传输历史页面。
- [ ] 使用后台线程处理扫描、打包、传输和写入。
- [ ] 使用 pytest-qt 覆盖关键交互。

## 验收标准

- [ ] 应用可以打开主窗口。
- [ ] 首次启动可以配置 Steam 路径。
- [ ] 可以从 GUI 进入发送和接收流程。
- [ ] 长任务不会卡住界面。
- [ ] 错误和风险提示清晰。
- [ ] UI 风格符合 Fluent 设计。

## 许可风险

`PySide6-Fluent-Widgets` 使用 GPLv3/商业双许可证。发布前需要确认项目许可证策略：

- 如果项目开源并兼容 GPLv3，可使用 GPLv3 方案。
- 如果项目闭源或商业分发，需要购买或确认商业授权。
