"""任务导出 API 路由"""

import urllib.parse
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional, List

from ..database import get_db
from ..export_service import generate_export_package, TASK_ATTR_OPTIONS, _sanitize_filename

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}", tags=["export"])


@router.get("/export")
def export_task_doc(
    project_id: str,
    task_id: str,
    start_date: Optional[str] = Query(None, description="沟通记录开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="沟通记录结束日期 (YYYY-MM-DD)"),
    fields: Optional[str] = Query(None, description="任务属性字段，逗号分隔"),
    comm_ids: Optional[str] = Query(None, description="沟通记录ID，逗号分隔，指定后忽略时间范围"),
    comm_minimal: Optional[str] = Query(None, description="沟通记录极简模式，为 '1' 时只显示内容和附件"),
    db: Session = Depends(get_db),
):
    """
    导出任务说明文档。
    
    返回一个 ZIP 压缩包，内含：
    1. DOCX 格式的说明文档（含内嵌图片）
    2. attachments/ 目录（所有附件原文）
    """
    # 解析字段
    selected_fields = None
    if fields is not None:
        if fields == '':
            selected_fields = []  # 显式空值：不显示任何任务属性
        else:
            field_list = [f.strip() for f in fields.split(',') if f.strip()]
            # 验证字段合法性
            valid_keys = set(TASK_ATTR_OPTIONS.keys())
            invalid = [f for f in field_list if f not in valid_keys]
            if invalid:
                raise HTTPException(400, f"无效的任务属性字段: {', '.join(invalid)}。有效字段: {', '.join(valid_keys)}")
            selected_fields = field_list

    try:
        # 解析 comm_ids
        selected_comm_ids = None
        if comm_ids:
            id_list = [i.strip() for i in comm_ids.split(',') if i.strip().isdigit()]
            if id_list:
                selected_comm_ids = [int(i) for i in id_list]

        zip_bytes, comm_count, att_count = generate_export_package(
            db, project_id, task_id,
            start_date=start_date,
            end_date=end_date,
            fields=selected_fields,
            comm_ids=selected_comm_ids,
            comm_minimal=comm_minimal == '1',
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"导出失败: {str(e)}")

    # 从 task 获取标题用于文件名
    from ..database import resolve_project, resolve_task
    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)

    file_ts = datetime.now().strftime("%Y%m%d%H%M%S")
    # 任务名可能含 / 等非法字符，须清理后再作文件名，否则浏览器会拒绝或截断
    filename = f'{_sanitize_filename(task.title) or "任务"}_{file_ts}.zip'
    # 对非 ASCII 字符进行 URL 编码
    encoded_filename = urllib.parse.quote(filename)

    return Response(
        content=zip_bytes,
        media_type='application/zip',
        headers={
            'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}",
            'Content-Length': str(len(zip_bytes)),
            'X-Export-Stats': f'comms:{comm_count}, atts:{att_count}',
        }
    )
