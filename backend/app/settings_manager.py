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
    "max_file_size_mb": 50,
    "autostart": {"mode": "off"},
    "backend_port": 8000,
    "frontend_port": 5173,
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


def remove_settings_key(key: str) -> dict:
    """从设置文件中移除指定键（如迁移完成后的旧配置键），返回最新设置"""
    current = load_settings()
    if key in current:
        current.pop(key)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
    return current


def get_max_file_size() -> int:
    """获取附件大小限制（字节）"""
    settings = load_settings()
    return settings["max_file_size_mb"] * 1024 * 1024


def get_port(key: str, default: int = None) -> int:
    """
    获取端口配置，优先级：环境变量 → settings.json → 默认值
    key 可选值: 'backend_port', 'frontend_port'
    环境变量: TASKM_BACKEND_PORT, TASKM_FRONTEND_PORT
    """
    env_map = {
        "backend_port": "TASKM_BACKEND_PORT",
        "frontend_port": "TASKM_FRONTEND_PORT",
    }
    env_name = env_map.get(key)
    if env_name:
        val = os.environ.get(env_name)
        if val and val.isdigit():
            return int(val)

    settings = load_settings()
    fallback = default if default is not None else DEFAULT_SETTINGS.get(key, 8000)
    return int(settings.get(key, fallback))


# ── 项目书签分类 ──
# 书签列表存于 settings.json 的 project_categories，结构：[{"key": "...", "name": "..."}]
def get_categories() -> list:
    """读取所有书签分类（有序列表）"""
    settings = load_settings()
    cats = settings.get("project_categories", [])
    return cats if isinstance(cats, list) else []


def save_categories(cats: list) -> list:
    """覆盖保存书签分类列表"""
    return save_settings({"project_categories": cats}).get("project_categories", [])


# ── 默认书签 ──
# 默认书签（最多 1 个）以 key 字符串存入 settings.json 的 default_category，
# 空串 / 缺失表示未设置，此时前端显示「全部项目」。
def get_default_category() -> str:
    """读取默认书签的 key，未设置返回空串"""
    settings = load_settings()
    val = settings.get("default_category", "")
    return val if isinstance(val, str) else ""


def set_default_category(key: str) -> str:
    """设置默认书签 key（'' 表示清除）。若 key 不在现有书签列表中则忽略设置。"""
    key = key or ""
    if key:
        cats = get_categories()
        if not any(c.get("key") == key for c in cats):
            raise ValueError("书签不存在")
    save_settings({"default_category": key})
    return key


# ── 薪资指标卡顺序 / 隐藏 ──
# 卡片 key 顺序存于 settings.json 的 salary_card_order（有序列表），
# 隐藏的卡片 key 存于 salary_card_hidden（列表）。结构与书签分类（project_categories）同模式。
SALARY_CARD_DEFAULT_ORDER = ["gross", "deduct", "net", "credited", "company", "taxcmp"]


def _normalize_card_order(order) -> list:
    """校验卡片 key：只保留合法且不重复的，缺失的卡按默认顺序补全（保证列表始终包含全部卡）"""
    if not isinstance(order, list):
        order = []
    seen = set()
    clean = []
    for k in order:
        if k in SALARY_CARD_DEFAULT_ORDER and k not in seen:
            seen.add(k)
            clean.append(k)
    for k in SALARY_CARD_DEFAULT_ORDER:
        if k not in seen:
            clean.append(k)
    return clean


def get_salary_card_order() -> list:
    """读取指标卡顺序；未配置 / 非法时返回默认顺序"""
    settings = load_settings()
    order = settings.get("salary_card_order")
    if not isinstance(order, list) or not order:
        return list(SALARY_CARD_DEFAULT_ORDER)
    return _normalize_card_order(order)


def save_salary_card_order(order) -> list:
    """覆盖保存指标卡顺序（校验 + 补全后写回）"""
    clean = _normalize_card_order(order)
    save_settings({"salary_card_order": clean})
    return clean


def get_salary_card_hidden() -> list:
    """读取隐藏的指标卡 key 列表"""
    settings = load_settings()
    hidden = settings.get("salary_card_hidden", [])
    if not isinstance(hidden, list):
        return []
    return [k for k in hidden if k in SALARY_CARD_DEFAULT_ORDER]


def save_salary_card_hidden(hidden) -> list:
    """覆盖保存隐藏的指标卡 key 列表（只保留合法 key）"""
    if not isinstance(hidden, list):
        hidden = []
    clean = [k for k in hidden if k in SALARY_CARD_DEFAULT_ORDER]
    save_settings({"salary_card_hidden": clean})
    return clean

