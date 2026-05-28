"""
应用全局设置管理
使用 JSON 文件持久化，位于 backend/settings.json
"""
import json
import os

# settings.json 存放在 backend 目录
SETTINGS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "settings.json"
)

DEFAULT_SETTINGS = {
    "max_file_size_mb": 50
}


def load_settings() -> dict:
    """读取所有设置，缺失的键用默认值补齐"""
    if not os.path.exists(SETTINGS_FILE):
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**DEFAULT_SETTINGS, **data}
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_SETTINGS)


def save_settings(data: dict) -> dict:
    """合并更新设置并写回文件"""
    current = load_settings()
    current.update(data)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    return current


def get_max_file_size() -> int:
    """获取附件大小限制（字节）"""
    settings = load_settings()
    return settings["max_file_size_mb"] * 1024 * 1024
