"""Simple qfluentwidgets GUI for scanning supported Steam games and save paths."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMainWindow,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    ListWidget,
    PrimaryPushButton,
    PushButton,
    TextEdit,
    TitleLabel,
    setThemeColor,
)

from config import AppConfig, SavePackage
from p2p_transport import DirectTcpSender, receive_archive
from received_installer import install_received_archive
from relay_client import create_relay_session, is_relay_transfer_key, receive_with_relay_fallback
from save_discovery import discover_supported_games, supported_game_names
from save_package_builder import build_save_archive
from steam_library import discover_installed_games, discover_steam_libraries
from utils import detect_steam_path


class MainWindow(QMainWindow):
    """A deliberately small first GUI pass."""

    transfer_log = Signal(str)
    transfer_warning = Signal(str)

    def __init__(self, config: AppConfig, config_path: str = "config.json") -> None:
        super().__init__()
        self.config = config
        self.config_path = config_path
        self.installed_game_count = 0
        self.current_sender: DirectTcpSender | None = None

        setThemeColor("#2b7de9")
        self.setWindowTitle("Game Save Transfer")
        self.resize(980, 880)
        self.setMinimumSize(860, 560)

        self._build_ui()
        self._connect_signals()
        self.refresh_view()
        QTimer.singleShot(0, self.auto_scan_on_startup)

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        header = QVBoxLayout()
        header.addWidget(TitleLabel("Game Save Transfer"))
        header.addWidget(
            CaptionLabel("先用 Steam 库识别支持的游戏，再扫描可直接发送的世界/存档包。")
        )
        root.addLayout(header)

        steam_card = CardWidget()
        steam_layout = QVBoxLayout(steam_card)
        steam_layout.setContentsMargins(18, 16, 18, 16)
        steam_layout.setSpacing(10)
        steam_layout.addWidget(BodyLabel("Steam 库配置"))

        path_row = QHBoxLayout()
        self.steam_path_edit = LineEdit()
        self.steam_path_edit.setPlaceholderText("Steam 根目录，例如 C:\\Program Files (x86)\\Steam")
        self.browse_steam_button = PushButton("选择 Steam 目录")
        self.detect_steam_button = PushButton("自动检测")
        self.scan_button = PrimaryPushButton("扫描支持的游戏")
        path_row.addWidget(self.steam_path_edit, 1)
        path_row.addWidget(self.browse_steam_button)
        path_row.addWidget(self.detect_steam_button)
        path_row.addWidget(self.scan_button)
        steam_layout.addLayout(path_row)

        relay_row = QHBoxLayout()
        relay_row.addWidget(BodyLabel("公网服务器"))
        self.relay_url_edit = LineEdit()
        self.relay_url_edit.setPlaceholderText("可选，例如 https://relay.example.com")
        relay_row.addWidget(self.relay_url_edit, 1)
        steam_layout.addLayout(relay_row)

        self.summary_label = CaptionLabel("")
        steam_layout.addWidget(self.summary_label)
        root.addWidget(steam_card)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_card = CardWidget()
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(18, 16, 18, 16)
        left_layout.setSpacing(10)
        left_layout.addWidget(BodyLabel("已支持的 Steam 游戏"))
        self.game_list = ListWidget()
        self.game_list.setMinimumWidth(310)
        left_layout.addWidget(self.game_list)

        right_card = CardWidget()
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(10)
        right_layout.addWidget(BodyLabel("可发送的世界 / 存档包"))
        self.save_path_list = ListWidget()
        right_layout.addWidget(self.save_path_list, 1)

        manual_row = QHBoxLayout()
        self.add_manual_path_button = PushButton("手动添加世界/存档目录")
        self.open_selected_path_button = PushButton("打开所选目录")
        manual_row.addWidget(self.add_manual_path_button)
        manual_row.addWidget(self.open_selected_path_button)
        manual_row.addStretch(1)
        right_layout.addLayout(manual_row)

        send_section = QVBoxLayout()
        send_section.addWidget(BodyLabel("发送给朋友"))
        send_section.addWidget(
            CaptionLabel("1. 选择一个世界/存档包。2. 生成发送密钥。3. 把密钥发给接收方。")
        )
        self.receive_key_edit = LineEdit()
        self.receive_key_edit.setPlaceholderText("在这里粘贴对方发来的配对密钥")
        self.create_pairing_button = PrimaryPushButton("生成发送密钥")
        self.send_key_edit = LineEdit()
        self.send_key_edit.setReadOnly(True)
        self.send_key_edit.setPlaceholderText("生成后的密钥会显示在这里")
        send_section.addWidget(self.create_pairing_button)
        send_section.addWidget(self.send_key_edit)
        right_layout.addLayout(send_section)

        receive_section = QVBoxLayout()
        receive_section.addWidget(BodyLabel("从朋友那里接收"))
        receive_section.addWidget(CaptionLabel("把对方生成的配对密钥粘贴到下面，接收后会自动解包到本机对应的存档目录。"))
        receive_row = QHBoxLayout()
        self.receive_button = PushButton("接收并安装存档")
        receive_row.addWidget(self.receive_key_edit, 1)
        receive_row.addWidget(self.receive_button)
        receive_section.addLayout(receive_row)
        right_layout.addLayout(receive_section)

        splitter.addWidget(left_card)
        splitter.addWidget(right_card)
        splitter.setSizes([360, 560])
        root.addWidget(splitter, 1)

        bottom = QHBoxLayout()
        log_card = CardWidget()
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(18, 16, 18, 16)
        log_layout.addWidget(BodyLabel("操作日志"))
        self.log_text = TextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(120)
        log_layout.addWidget(self.log_text)
        bottom.addWidget(log_card, 1)

        supported_card = CardWidget()
        supported_layout = QVBoxLayout(supported_card)
        supported_layout.setContentsMargins(18, 16, 18, 16)
        supported_layout.addWidget(BodyLabel("当前内置规则"))
        supported_label = QLabel("\n".join(supported_game_names()))
        supported_label.setWordWrap(True)
        supported_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        supported_layout.addWidget(supported_label)
        bottom.addWidget(supported_card)

        root.addLayout(bottom)
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.browse_steam_button.clicked.connect(self.choose_steam_root)
        self.detect_steam_button.clicked.connect(self.detect_steam_root)
        self.scan_button.clicked.connect(self.scan_supported_games)
        self.game_list.currentItemChanged.connect(self.show_selected_game_saves)
        self.add_manual_path_button.clicked.connect(self.add_manual_save_path)
        self.open_selected_path_button.clicked.connect(self.open_selected_save_path)
        self.create_pairing_button.clicked.connect(self.create_pairing_for_selected_package)
        self.receive_button.clicked.connect(self.receive_package_from_key)
        self.relay_url_edit.editingFinished.connect(self.save_relay_server_url)
        self.transfer_log.connect(self.log)
        self.transfer_warning.connect(self.warn)

    def refresh_view(self) -> None:
        self.steam_path_edit.setText(self.config.steam_root)
        self.relay_url_edit.setText(self.config.relay_server_url)
        self.game_list.clear()

        for game in sorted(self.config.known_games, key=lambda item: item.name.casefold()):
            if game.save_packages:
                suffix = f" · {len(game.save_packages)} 个可发送项"
            elif game.save_paths:
                suffix = " · 找到根目录，未识别世界"
            else:
                suffix = " · 未找到存档"
            item = QListWidgetItem(f"{game.name} ({game.app_id}){suffix}")
            item.setData(Qt.ItemDataRole.UserRole, game.app_id)
            self.game_list.addItem(item)

        if self.game_list.count() > 0:
            self.game_list.setCurrentRow(0)
        else:
            self.save_path_list.clear()

        self.summary_label.setText(
            f"Steam 库: {len(self.config.steam_libraries)} 个；"
            f"已安装游戏: {self.installed_game_count} 个；"
            f"当前支持: {len(self.config.known_games)} 个。"
        )

    def choose_steam_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择 Steam 根目录")
        if not directory:
            return

        self.config.steam_root = directory
        self.config.save(self.config_path)
        self.refresh_view()
        self.log(f"已设置 Steam 目录: {directory}")

    def detect_steam_root(self) -> None:
        steam_root = detect_steam_path()
        if not steam_root:
            self.warn("没有自动检测到 Steam，请手动选择目录。")
            return

        self.config.steam_root = steam_root
        self.config.save(self.config_path)
        self.refresh_view()
        self.log(f"自动检测到 Steam 目录: {steam_root}")

    def scan_supported_games(self) -> None:
        steam_root = self.steam_path_edit.text().strip()
        self.run_scan(steam_root, show_warnings=True)

    def save_relay_server_url(self) -> None:
        self.config.relay_server_url = self.relay_url_edit.text().strip()
        self.config.save(self.config_path)
        if self.config.relay_server_url:
            self.log(f"已设置公网服务器: {self.config.relay_server_url}")

    def auto_scan_on_startup(self) -> None:
        """Refresh known games and save packages when the app opens."""
        steam_root = self.config.steam_root or self.steam_path_edit.text().strip()
        if not steam_root:
            detected = detect_steam_path()
            if detected:
                steam_root = detected
                self.config.steam_root = detected

        if not steam_root:
            self.log("启动时没有可用的 Steam 路径，等待用户选择。")
            return

        self.run_scan(steam_root, show_warnings=False)

    def run_scan(self, steam_root: str, show_warnings: bool) -> None:
        """Scan Steam libraries and refresh supported save packages."""
        if not steam_root:
            if show_warnings:
                self.warn("请先选择或输入 Steam 根目录。")
            return

        if not Path(steam_root).exists():
            if show_warnings:
                self.warn("Steam 根目录不存在，请检查路径。")
            else:
                self.log(f"启动自动扫描跳过：Steam 根目录不存在：{steam_root}")
            return

        self.config.steam_root = steam_root
        self.config.steam_libraries = discover_steam_libraries(steam_root)
        installed_games = discover_installed_games(steam_root)
        supported_games = discover_supported_games(
            installed_games,
            steam_root,
            self.config.save_location_templates,
        )

        self.installed_game_count = len(installed_games)
        for game in supported_games:
            self.config.add_game(game)

        self.config.save(self.config_path)
        self.refresh_view()
        action = "扫描完成" if show_warnings else "启动自动扫描完成"
        self.log(
            f"{action}：发现 {len(self.config.steam_libraries)} 个 Steam 库，"
            f"{len(installed_games)} 个已安装游戏，"
            f"{len(supported_games)} 个有内置存档规则。"
        )

        if show_warnings and not supported_games:
            self.warn("没有发现当前内置规则支持的游戏；你可以之后添加更多规则。")

    def show_selected_game_saves(self) -> None:
        self.save_path_list.clear()
        game = self.current_game()
        if not game:
            return

        if not game.save_packages:
            if game.save_paths:
                for path in game.save_paths:
                    item = QListWidgetItem(f"存档根目录（未识别具体世界）\n{path}")
                    item.setData(Qt.ItemDataRole.UserRole, path)
                    self.save_path_list.addItem(item)
                self.log("已找到存档根目录，但暂未识别具体世界。可以打开根目录手动确认。")
                return

            placeholder = QListWidgetItem("暂未找到可发送项。可以点击“手动添加世界/存档目录”。")
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.save_path_list.addItem(placeholder)
            return

        for package in game.save_packages:
            item = QListWidgetItem(f"{package.label}\n{package.path}")
            item.setData(Qt.ItemDataRole.UserRole, package.id)
            self.save_path_list.addItem(item)

    def add_manual_save_path(self) -> None:
        game = self.current_game()
        if not game:
            self.warn("请先选择一个游戏。")
            return

        directory = QFileDialog.getExistingDirectory(self, f"选择 {game.name} 的世界/存档目录")
        if not directory:
            return

        if directory not in [package.path for package in game.save_packages]:
            game.save_packages.append(
                SavePackage(
                    id=f"{game.app_id}:manual:{directory}",
                    label=Path(directory).name,
                    path=directory,
                    root_path=directory,
                    include_patterns=["**/*"],
                    exclude_patterns=["**/*.log"],
                    metadata={"manual": "true", "app_id": game.app_id},
                )
            )
            self.config.add_game(game)
            self.config.save(self.config_path)

        self.refresh_view()
        self.log(f"已为 {game.name} 添加可发送目录: {directory}")

    def open_selected_save_path(self) -> None:
        item = self.save_path_list.currentItem()
        game = self.current_game()
        if not item and game and game.save_paths:
            path = game.save_paths[0]
        elif item:
            path = self.path_from_save_list_item(item)
        else:
            self.warn("请先选择一个存档目录；如果还没有结果，可以先重新扫描或手动添加。")
            return

        if not path or not Path(path).exists():
            self.warn("所选目录不存在。")
            return

        os.startfile(path)

    def create_pairing_for_selected_package(self) -> None:
        package = self.current_package()
        if not package:
            self.warn("请先选择一个可发送的世界/存档包。")
            return

        try:
            archive = build_save_archive(package, "outgoing")
            sender = DirectTcpSender(archive)
            pairing_key = sender.start()
            relay_url = self.relay_url_edit.text().strip()
            if relay_url:
                relay_session = create_relay_session(relay_url, pairing_key, archive)
                key_text = relay_session.transfer_key
                self.config.relay_server_url = relay_url
                self.config.save(self.config_path)
            else:
                key_text = pairing_key.encode()
        except Exception as e:
            self.warn(f"创建发送会话失败: {e}")
            return

        self.current_sender = sender
        self.send_key_edit.setText(key_text)
        if self.relay_url_edit.text().strip():
            self.log("已生成公网发送密钥，并上传中继兜底包。复制给接收方。")
        else:
            self.log("已生成局域网直连密钥。跨公网请配置公网服务器。")
        self.log(key_text)

        thread = threading.Thread(target=self._serve_current_sender, daemon=True)
        thread.start()

    def receive_package_from_key(self) -> None:
        key_text = self.receive_key_edit.text().strip()
        if not key_text:
            self.warn("请先粘贴配对密钥。")
            return

        thread = threading.Thread(
            target=self._receive_package_worker,
            args=(key_text,),
            daemon=True,
        )
        thread.start()

    def current_package(self) -> SavePackage | None:
        item = self.save_path_list.currentItem()
        game = self.current_game()
        if not item or not game:
            return None

        package_id = item.data(Qt.ItemDataRole.UserRole)
        for package in game.save_packages:
            if package.id == package_id:
                return package
        return None

    def path_from_save_list_item(self, item: QListWidgetItem) -> str | None:
        game = self.current_game()
        value = item.data(Qt.ItemDataRole.UserRole)
        if game:
            for package in game.save_packages:
                if package.id == value:
                    return package.path
        return value

    def _serve_current_sender(self) -> None:
        sender = self.current_sender
        if not sender:
            return

        try:
            sender.serve_once()
            self.transfer_log.emit("发送完成。")
        except Exception as e:
            self.transfer_warning.emit(f"发送失败: {e}")
        finally:
            sender.close()
            self.current_sender = None

    def _receive_package_worker(self, key_text: str) -> None:
        try:
            if is_relay_transfer_key(key_text):
                archive_path = receive_with_relay_fallback(key_text, "incoming")
            else:
                archive_path = receive_archive(key_text, "incoming").archive_path
            received_path = archive_path
            installed = install_received_archive(received_path, self.config)
            self.transfer_log.emit(
                f"接收并安装完成: {installed.target_path}，文件数: {installed.file_count}"
            )
        except Exception as e:
            self.transfer_warning.emit(f"接收失败: {e}")

    def current_game(self):
        item = self.game_list.currentItem()
        if not item:
            return None
        return self.config.get_game(item.data(Qt.ItemDataRole.UserRole))

    def log(self, message: str) -> None:
        self.log_text.append(message)

    def warn(self, message: str) -> None:
        self.log(message)
        InfoBar.warning(
            title="提示",
            content=message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )
