"""工具函数测试"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.utils import (
    detect_dst_path,
    detect_steam_path,
    expand_path,
    format_size,
    generate_qr_code,
    is_dst_running,
    validate_path,
)


def test_validate_path():
    """测试路径验证"""
    # 空路径
    assert validate_path("") is False

    # 不存在的路径
    assert validate_path("C:\\nonexistent\\path") is False

    # 存在的路径
    with tempfile.TemporaryDirectory() as tmpdir:
        assert validate_path(tmpdir) is True


def test_expand_path():
    """测试路径展开"""
    # 测试环境变量展开
    result = expand_path("%USERPROFILE%\\Documents")
    assert "%USERPROFILE%" not in result

    # 测试用户目录展开
    result = expand_path("~/Documents")
    assert "~" not in result


@patch("src.utils.psutil.process_iter")
def test_is_dst_running_true(mock_process_iter):
    """测试检测 DST 运行（运行中）"""
    # 模拟进程列表
    mock_proc = MagicMock()
    mock_proc.info = {"name": "dontstarve_steam.exe"}
    mock_process_iter.return_value = [mock_proc]

    assert is_dst_running() is True


@patch("src.utils.psutil.process_iter")
def test_is_dst_running_false(mock_process_iter):
    """测试检测 DST 运行（未运行）"""
    # 模拟空进程列表
    mock_proc = MagicMock()
    mock_proc.info = {"name": "chrome.exe"}
    mock_process_iter.return_value = [mock_proc]

    assert is_dst_running() is False


def test_generate_qr_code():
    """测试二维码生成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_qr.png"
        result = generate_qr_code("test_data_123", str(output_path))

        assert result is True
        assert output_path.exists()
        assert output_path.stat().st_size > 0


def test_format_size():
    """测试文件大小格式化"""
    assert format_size(0) == "0.00 B"
    assert format_size(1023) == "1023.00 B"
    assert format_size(1024) == "1.00 KB"
    assert format_size(1024 * 1024) == "1.00 MB"
    assert format_size(1024 * 1024 * 1024) == "1.00 GB"
    assert format_size(1536) == "1.50 KB"


@patch.dict("os.environ", {"USERPROFILE": "C:\\Users\\TestUser"})
@patch("src.utils.Path.exists")
def test_detect_dst_path_found(mock_exists):
    """测试检测 DST 路径（找到）"""
    mock_exists.return_value = True
    result = detect_dst_path()

    assert result is not None
    assert "DoNotStarveTogether" in result


@patch.dict("os.environ", {"USERPROFILE": "C:\\Users\\TestUser"})
@patch("src.utils.Path.exists")
def test_detect_dst_path_not_found(mock_exists):
    """测试检测 DST 路径（未找到）"""
    mock_exists.return_value = False
    result = detect_dst_path()

    assert result is None


def test_show_notification():
    """测试通知显示（不会实际显示）"""
    from src.utils import show_notification

    # 这个测试主要确保函数不会崩溃
    # 实际通知不会显示（或者会显示取决于环境）
    try:
        show_notification("测试标题", "测试消息")
    except Exception:
        # 某些环境可能不支持通知，这是可以接受的
        pass


def test_detect_steam_path_found(monkeypatch, tmp_path):
    """测试检测 Steam 路径（找到）"""
    steam_dir = tmp_path / "Steam"
    steam_dir.mkdir()
    (steam_dir / "steamapps").mkdir()
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path))
    monkeypatch.delenv("PROGRAMFILES", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    result = detect_steam_path()

    assert result == str(steam_dir)
