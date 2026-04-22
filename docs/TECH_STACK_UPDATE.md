# 技术栈更新说明

**最后更新**: 2026-04-22

## 新方向

项目从“DST/Syncthing 存档同步工具”调整为“小规模 P2P 游戏存档传输工具”。技术栈也需要随之调整：

- 下线 Syncthing 作为核心依赖。
- 引入 Steam 游戏库扫描和存档规则系统。
- GUI 使用 PySide6 + qfluentwidgets。
- 传输层采用抽象接口，先做原型验证再固定底层 P2P 实现。

## 当前推荐技术栈

| 类别 | 技术 | 说明 |
| --- | --- | --- |
| 语言 | Python 3.11+ | 保持当前版本要求 |
| GUI | PySide6 | Qt for Python |
| Fluent UI | PySide6-Fluent-Widgets | 导入包名为 `qfluentwidgets` |
| 配置 | Pydantic | 配置模型和迁移 |
| 日志 | Loguru | 保持当前实现 |
| 进程检测 | psutil | 检测游戏是否运行 |
| 文件打包 | zipfile / py7zr | 存档包和快照 |
| 校验 | hashlib | 文件完整性校验 |
| 测试 | pytest / pytest-qt | 单元测试和 GUI 测试 |
| 打包 | PyInstaller | Windows exe |

## 待验证技术

P2P 底层还不应过早定死，建议做 spike：

1. WebRTC DataChannel。
2. libp2p。
3. 局域网 TCP 原型。
4. 可选临时中继兜底。

## 依赖变更

新增：

```text
PySide6-Fluent-Widgets>=1.11.2
```

保留：

```text
PySide6>=6.6.0
pydantic>=2.5.0
loguru>=0.7.2
psutil>=5.9.8
pytest>=8.0.0
pytest-qt>=4.3.0
```

降级为可选或待移除：

```text
httpx
segno
winotify
plyer
py7zr
```

其中 `segno` 仍可用于二维码；`httpx` 可能在未来信令服务或更新检查中使用，但不再是 Syncthing API 的核心依赖。

## 许可注意

PySide6-Fluent-Widgets 当前为 GPLv3/商业双许可证。不要忽略这个点：如果项目未来不是 GPLv3 兼容开源发布，需要提前处理商业授权。


