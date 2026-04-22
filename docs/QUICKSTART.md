# 快速开始

本项目当前正在从“游戏存档同步工具”调整为“小规模 P2P 游戏存档传输工具”。当前代码仍处在基础阶段，GUI 和真实 P2P 传输尚未完成。

## 1. 安装依赖

推荐使用 `uv`：

```bash
setup_dev.bat
```

或手动执行：

```bash
uv sync --group dev
```

## 2. 运行当前入口

```bash
uv run python src\main.py
```

当前入口会：

- 初始化日志。
- 创建/读取配置。
- 尝试检测 Steam 路径。
- 解析 Steam Library 与已安装游戏清单。
- 创建安全快照目录。
- 输出当前开发阶段提示。

## 3. 运行测试

```bash
uv run pytest
```

如果本机使用 pyenv，请先设置 Python 版本或创建 `.venv`，否则 `pytest` 可能被 pyenv shim 拦截。

## 4. 当前还不能做什么

- 还不能真实建立 P2P 连接。
- 还不能传输存档。
- 还没有 qfluentwidgets GUI。
- 还没有游戏存档规则扫描。

## 5. 下一步开发入口

建议按这个顺序推进：

1. 配置模型和测试已经开始迁移到新方向。
2. 完善 Steam Library 解析与异常兼容。
3. 实现游戏存档发现规则。
4. 做 P2P/局域网传输原型。
5. 再实现 qfluentwidgets GUI。


