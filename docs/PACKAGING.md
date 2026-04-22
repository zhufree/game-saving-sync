# Windows 打包说明

本项目使用 PyInstaller 打包 Windows 桌面客户端。

## 一键打包

在 Windows 项目根目录执行：

```bat
package_app.bat
```

打包完成后会生成：

```text
dist\GameSaveTransfer\GameSaveTransfer.exe
dist\GameSaveTransfer-windows-x64.zip
```

发给朋友测试时，推荐发送：

```text
dist\GameSaveTransfer-windows-x64.zip
```

对方解压后运行：

```text
GameSaveTransfer.exe
```

不要只单独发送 `GameSaveTransfer.exe`，因为 onedir 模式还需要旁边的 `_internal` 依赖目录。

## 手动打包命令

```bat
.venv\Scripts\python.exe -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name GameSaveTransfer ^
  --paths src ^
  --hidden-import qfluentwidgets ^
  --hidden-import qframelesswindow ^
  src\main.py
```

然后压缩：

```powershell
Compress-Archive -Path dist\GameSaveTransfer\* -DestinationPath dist\GameSaveTransfer-windows-x64.zip -CompressionLevel Optimal
```

## 依赖准备

如果还没有开发环境：

```bat
setup_dev.bat
```

或者：

```bash
uv sync --group dev
```

如果 PyInstaller 没安装，`package_app.bat` 会尝试自动安装到 `.venv`。

## 当前产物说明

- 当前打包的是客户端 GUI。
- 中继/信令服务器仍然通过源码运行：

```bash
uv run python src/relay_server.py --host 0.0.0.0 --port 8765 --storage ./relay_storage
```

服务器部署见：

```text
RELAY_SERVER.md
```

## 常见问题

### 为什么不是单文件 exe？

当前先使用 PyInstaller onedir 模式，因为 PySide6/qfluentwidgets 依赖较多，onedir 更稳定、启动更快、问题更少。

### 运行后配置文件在哪里？

当前 MVP 仍然会在 exe 所在目录附近生成：

```text
config.json
logs\
incoming\
outgoing\
snapshots\
```

这些都不应该提交到 Git。

### Windows 安全提示怎么办？

未签名 exe 可能触发 Windows SmartScreen。测试阶段可以选择“更多信息 -> 仍要运行”。正式发布前应考虑代码签名。
