from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db, ProjectContact, Contact, CommunicationContact, touch_project, resolve_project
from .. import schemas

router = APIRouter(prefix="/projects/{project_id}/contacts", tags=["project_contacts"])


@router.get("", response_model=List[schemas.ProjectContactOut])
def get_project_contacts(
    project_id: str,
    search: Optional[str] = None,
    show_inactive: bool = False,
    db: Session = Depends(get_db)
):
    """获取项目对接人库列表，支持搜索，按首字母排序"""
    proj = resolve_project(db, project_id)
    query = db.query(ProjectContact).filter(ProjectContact.project_id == proj.id)
    
    if not show_inactive:
        query = query.filter(ProjectContact.is_active == True)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (ProjectContact.name.like(search_pattern)) |
            (ProjectContact.role.like(search_pattern)) |
            (ProjectContact.contact_info.like(search_pattern))
        )
    
    contacts = query.all()
    
    # 按首字母排序（中文按拼音首字母，英文按字母）
    def get_sort_key(contact):
        name = contact.name or ""
        # 简单处理：提取首字符
        first_char = name[0] if name else ""
        # 如果是中文字符，尝试获取拼音首字母（这里简单处理，直接按 Unicode 排序）
        return first_char.lower()
    
    contacts.sort(key=get_sort_key)
    return contacts


@router.post("", response_model=schemas.ProjectContactOut)
def add_project_contact(
    project_id: str,
    contact: schemas.ProjectContactCreate,
    db: Session = Depends(get_db)
):
    """添加项目对接人（自动激活同名非活动项）"""
    proj = resolve_project(db, project_id)
    # 检查是否已存在同名活跃项
    existing_active = db.query(ProjectContact).filter(
        ProjectContact.project_id == proj.id,
        ProjectContact.name == contact.name,
        ProjectContact.is_active == True
    ).first()
    
    if existing_active:
        raise HTTPException(status_code=400, detail="该对接人已存在于项目库中")
    
    # 检查同名非活动项，重新激活
    inactive = db.query(ProjectContact).filter(
        ProjectContact.project_id == proj.id,
        ProjectContact.name == contact.name,
        ProjectContact.is_active == False
    ).first()
    if inactive:
        update_data = contact.dict()
        for field, value in update_data.items():
            setattr(inactive, field, value)
        inactive.is_active = True
        db.commit()
        db.refresh(inactive)
        touch_project(db, proj.id)
        return inactive
    
    db_contact = ProjectContact(
        project_id=proj.id,
        name=contact.name,
        role=contact.role,
        contact_info=contact.contact_info
    )
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    touch_project(db, proj.id)
    return db_contact


@router.put("/{contact_id}", response_model=schemas.ProjectContactOut)
def update_project_contact(
    project_id: str,
    contact_id: int,
    contact_update: schemas.ProjectContactUpdate,
    db: Session = Depends(get_db)
):
    """更新项目对接人"""
    proj = resolve_project(db, project_id)
    db_contact = db.query(ProjectContact).filter(
        ProjectContact.id == contact_id,
        ProjectContact.project_id == proj.id
    ).first()
    
    if not db_contact:
        raise HTTPException(status_code=404, detail="对接人不存在")
    
    update_data = contact_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_contact, field, value)
    
    db.commit()
    db.refresh(db_contact)
    touch_project(db, proj.id)
    return db_contact


def _count_contact_refs(db: Session, contact_id: int) -> dict:
    """统计项目对接人被引用的次数"""
    count = db.query(Contact).filter(Contact.project_contact_id == contact_id).count()
    return {"任务对接人": count} if count else {}

def _clear_contact_refs(db: Session, contact_id: int):
    """彻底删除项目对接人时，删除所有关联的任务对接人及其沟通记录关联"""
    # 查出所有关联的 Contact id
    ids = [r[0] for r in db.query(Contact.id).filter(Contact.project_contact_id == contact_id).all()]
    if ids:
        # 清理 CommunicationContact 关联
        db.query(CommunicationContact).filter(CommunicationContact.contact_id.in_(ids)).delete(
            synchronize_session=False
        )
        # 删除 Contact 行
        db.query(Contact).filter(Contact.project_contact_id == contact_id).delete(
            synchronize_session=False
        )


@router.delete("/{contact_id}")
def delete_project_contact(
    project_id: str,
    contact_id: int,
    force: bool = False,
    confirmed: bool = False,
    db: Session = Depends(get_db)
):
    """删除项目对接人（软删除 / 彻底删除）"""
    proj = resolve_project(db, project_id)
    db_contact = db.query(ProjectContact).filter(
        ProjectContact.id == contact_id,
        ProjectContact.project_id == proj.id
    ).first()
    
    if not db_contact:
        raise HTTPException(status_code=404, detail="对接人不存在")
    
    if force:
        refs = _count_contact_refs(db, contact_id)
        if refs and not confirmed:
            raise HTTPException(409, detail={"message": "有数据引用该对接人", "refs": refs})
        _clear_contact_refs(db, contact_id)
        db.delete(db_contact)
        db.commit()
        touch_project(db, proj.id)
        return {"ok": True, "refs_cleaned": refs}
    
    db_contact.is_active = False
    db.commit()
    touch_project(db, proj.id)
    return {"ok": True}
