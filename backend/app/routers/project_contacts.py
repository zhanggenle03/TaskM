from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db, ProjectContact
from .. import schemas

router = APIRouter(prefix="/projects/{project_id}/contacts", tags=["project_contacts"])


@router.get("", response_model=List[schemas.ProjectContactOut])
def get_project_contacts(
    project_id: int,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取项目对接人库列表，支持搜索，按首字母排序"""
    query = db.query(ProjectContact).filter(ProjectContact.project_id == project_id)
    
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
    project_id: int,
    contact: schemas.ProjectContactCreate,
    db: Session = Depends(get_db)
):
    """添加项目对接人"""
    # 检查是否已存在（同一项目下同名对接人）
    existing = db.query(ProjectContact).filter(
        ProjectContact.project_id == project_id,
        ProjectContact.name == contact.name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="该对接人已存在于项目库中")
    
    db_contact = ProjectContact(
        project_id=project_id,
        name=contact.name,
        role=contact.role,
        contact_info=contact.contact_info
    )
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact


@router.put("/{contact_id}", response_model=schemas.ProjectContactOut)
def update_project_contact(
    project_id: int,
    contact_id: int,
    contact_update: schemas.ProjectContactUpdate,
    db: Session = Depends(get_db)
):
    """更新项目对接人"""
    db_contact = db.query(ProjectContact).filter(
        ProjectContact.id == contact_id,
        ProjectContact.project_id == project_id
    ).first()
    
    if not db_contact:
        raise HTTPException(status_code=404, detail="对接人不存在")
    
    update_data = contact_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_contact, field, value)
    
    db.commit()
    db.refresh(db_contact)
    return db_contact


@router.delete("/{contact_id}")
def delete_project_contact(
    project_id: int,
    contact_id: int,
    db: Session = Depends(get_db)
):
    """删除项目对接人"""
    db_contact = db.query(ProjectContact).filter(
        ProjectContact.id == contact_id,
        ProjectContact.project_id == project_id
    ).first()
    
    if not db_contact:
        raise HTTPException(status_code=404, detail="对接人不存在")
    
    db.delete(db_contact)
    db.commit()
    return {"ok": True}
