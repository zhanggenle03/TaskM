"""
项目书签分类路由
书签（分类）为全局概念，名称与顺序持久化在 settings.json 的 project_categories。
每个项目通过 projects.category 字段记录所属分类的 key（空串 = 未分类）。
"""
import uuid

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db, Project
from ..settings_manager import get_categories, save_categories, get_default_category, set_default_category


router = APIRouter(prefix="/categories", tags=["categories"])


# ── 请求体 ──
class CategoryCreate(BaseModel):
    name: str


class CategoryRename(BaseModel):
    name: str


class CategoryReorder(BaseModel):
    order: list[str]  # 书签 key 的有序列表


def _gen_key() -> str:
    return "cat_" + uuid.uuid4().hex[:8]


# ── 列表 ──
@router.get("")
def list_categories():
    """返回全部书签分类（有序）"""
    return get_categories()


# ── 默认书签 ──
class CategoryDefault(BaseModel):
    key: str = ""   # 书签 key；空串表示清除默认（数量恒 ≤ 1）


@router.get("/default")
def get_default():
    """读取默认书签 key（'' 表示未设置，前端显示全部）"""
    return {"key": get_default_category()}


@router.put("/default")
def set_default(body: CategoryDefault):
    """设置 / 清除默认书签（最多 1 个）"""
    try:
        key = set_default_category(body.key)
    except ValueError:
        raise HTTPException(400, "书签不存在")
    return {"key": key}


# ── 新增 ──
@router.post("")
def create_category(body: CategoryCreate):
    """新增一个书签分类，名称可自定义"""
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "书签名称不能为空")
    cats = get_categories()
    # 同名检测（忽略大小写），避免重复书签
    if any(c["name"].lower() == name.lower() for c in cats):
        raise HTTPException(400, "已存在同名书签")
    cat = {"key": _gen_key(), "name": name}
    cats.append(cat)
    save_categories(cats)
    return cat


# ── 重命名 ──
@router.put("/{key}")
def rename_category(key: str, body: CategoryRename):
    """重命名书签（不影响已归类项目，因为项目记录的是 key）"""
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "书签名称不能为空")
    cats = get_categories()
    target = next((c for c in cats if c["key"] == key), None)
    if not target:
        raise HTTPException(404, "书签不存在")
    # 同名（他人）检测
    if any(c["key"] != key and c["name"].lower() == name.lower() for c in cats):
        raise HTTPException(400, "已存在同名书签")
    target["name"] = name
    save_categories(cats)
    return target


# ── 删除 ──
@router.delete("/{key}")
def delete_category(key: str, db: Session = Depends(get_db)):
    """删除书签，并把所属项目的分类置空（变为未分类）"""
    cats = get_categories()
    target = next((c for c in cats if c["key"] == key), None)
    if not target:
        raise HTTPException(404, "书签不存在")
    # 解除相关项目的分类引用
    db.query(Project).filter(Project.category == key).update(
        {Project.category: ""}, synchronize_session=False
    )
    db.commit()
    # 从书签列表移除
    cats = [c for c in cats if c["key"] != key]
    save_categories(cats)
    # 若删除的是默认书签，清除默认设置
    if get_default_category() == key:
        set_default_category("")
    return {"ok": True}


# ── 排序 ──
@router.put("/reorder")
def reorder_categories(body: CategoryReorder):
    """按给定 key 顺序重排书签"""
    cats = get_categories()
    by_key = {c["key"]: c for c in cats}
    ordered = [by_key[k] for k in body.order if k in by_key]
    # 补回未在 order 中出现的（容错）
    for c in cats:
        if c["key"] not in body.order:
            ordered.append(c)
    save_categories(ordered)
    return ordered
