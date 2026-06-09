"""任务导出服务 —— 生成 DOCX 文档 + 附件 ZIP 包"""

import os
import io
import zipfile
from datetime import datetime
from typing import Optional, List

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from sqlalchemy.orm import Session
from .database import (
    Communication, Attachment, Contact, StatusPool,
    TagPool, TaskTag, Project,
    UPLOAD_DIR, derive_task_status
)

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.ico'}

TASK_ATTR_OPTIONS = {
    'title': '任务名称', 'display_id': '显示ID', 'status': '状态',
    'priority': '优先级', 'due_date': '截止日期', 'description': '描述',
    'created_at': '创建时间', 'updated_at': '更新时间',
    'contacts': '对接人', 'tags': '标签',
}

PRIORITY_LABELS = {'low': '低', 'normal': '普通', 'high': '高', 'urgent': '紧急'}

# 公文风格字号常量
FONT_FAMILY = '仿宋'
FONT_FAMILY_HEADING = '黑体'
BODY_SIZE = Pt(12)        # 小四
SMALL_SIZE = Pt(10)       # 五号
HEADING1_SIZE = Pt(16)    # 三号
HEADING2_SIZE = Pt(14)    # 四号
TITLE_SIZE = Pt(22)       # 二号
SUBTITLE_SIZE = Pt(14)    # 四号


def _set_cell_shading(cell, color: str):
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), color)
    shading.set(qn('w:val'), 'clear')
    cell._tc.get_or_add_tcPr().append(shading)


def _set_run_font(run, size=BODY_SIZE, bold=False, color=None, font_name=FONT_FAMILY):
    """为 run 设置标准的公文风格字体"""
    run.bold = bold
    run.font.size = size
    run.font.name = font_name
    if color:
        run.font.color.rgb = color
    # 设置东亚字体
    r_elem = run._element
    rPr = r_elem.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:eastAsia'), font_name)
    return run


def _add_run(paragraph, text, size=BODY_SIZE, bold=False, color=None, font_name=FONT_FAMILY):
    """添加 run 并设置公文风格字体"""
    run = paragraph.add_run(text)
    _set_run_font(run, size=size, bold=bold, color=color, font_name=font_name)
    return run


def _new_paragraph(doc, text='', size=BODY_SIZE, bold=False, color=None,
                   font_name=FONT_FAMILY, alignment=None,
                   before=0, after=0, first_line_indent=None):
    """创建新段落并设置公文格式"""
    p = doc.add_paragraph()
    if alignment:
        p.alignment = alignment
    if text:
        _add_run(p, text, size=size, bold=bold, color=color, font_name=font_name)

    # 设置段落间距
    pPr = p._p.get_or_add_pPr()
    spacing = OxmlElement('w:spacing')
    if before:
        spacing.set(qn('w:before'), str(before))
    if after:
        spacing.set(qn('w:after'), str(after))
    spacing.set(qn('w:line'), '360')  # 1.5 倍行距
    spacing.set(qn('w:lineRule'), 'auto')
    pPr.append(spacing)

    # 首行缩进
    if first_line_indent:
        ind = OxmlElement('w:ind')
        ind.set(qn('w:firstLine'), str(first_line_indent))
        pPr.append(ind)

    return p


def _add_hyperlink(paragraph, text, url, size=Pt(12)):
    """在段落中添加超链接（蓝色+下划线）"""
    part = paragraph.part
    r_id = part.relate_to(
        url,
        'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',
        is_external=True
    )
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)

    r_elem = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')

    # 字体
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:eastAsia'), FONT_FAMILY)
    rPr.append(rFonts)
    # 字号
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), str(size.pt * 2))
    rPr.append(sz)
    szCs = OxmlElement('w:szCs')
    szCs.set(qn('w:val'), str(size.pt * 2))
    rPr.append(szCs)
    # 蓝色
    c = OxmlElement('w:color')
    c.set(qn('w:val'), '0066CC')
    rPr.append(c)
    # 下划线
    u = OxmlElement('w:u')
    u.set(qn('w:val'), 'single')
    rPr.append(u)

    r_elem.append(rPr)
    t_elem = OxmlElement('w:t')
    t_elem.text = text
    r_elem.append(t_elem)
    hyperlink.append(r_elem)
    paragraph._p.append(hyperlink)
    return hyperlink


def _set_heading_style(doc, level, font_name=FONT_FAMILY_HEADING, size=HEADING1_SIZE):
    """设置标题样式"""
    style = doc.styles[f'Heading {level}']
    style.font.name = font_name
    style.font.size = size
    style.font.bold = True
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
    # 段落格式
    pPr = style.element.get_or_add_pPr()
    spacing = pPr.find(qn('w:spacing'))
    if spacing is None:
        spacing = OxmlElement('w:spacing')
        pPr.append(spacing)
    spacing.set(qn('w:before'), '200')
    spacing.set(qn('w:after'), '200')
    spacing.set(qn('w:line'), '360')
    spacing.set(qn('w:lineRule'), 'auto')


def build_export_data(
    db: Session,
    project_id: str,
    task_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fields: Optional[List[str]] = None,
    comm_ids: Optional[List[int]] = None,
) -> dict:
    """查询并整理导出数据"""
    from .database import resolve_project, resolve_task

    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)

    derived_status = derive_task_status(db, task.id)
    if derived_status is not None:
        task.status_id = derived_status

    project_info = db.query(Project).filter(Project.id == proj.id).first()
    status_pool = {s.id: s for s in db.query(StatusPool).filter(StatusPool.project_id == proj.id).all()}

    tag_rows = db.query(TaskTag).filter(TaskTag.task_id == task.id).all()
    tag_ids = [tr.tag_id for tr in tag_rows]
    tag_info = {}
    if tag_ids:
        for t in db.query(TagPool).filter(TagPool.id.in_(tag_ids)).all():
            tag_info[t.id] = t

    comm_query = db.query(Communication).filter(
        Communication.task_id == task.id
    ).order_by(Communication.comm_at, Communication.id)
    communications = comm_query.all()

    if start_date:
        try:
            sd = datetime.strptime(start_date, '%Y-%m-%d')
            communications = [c for c in communications if c.comm_at >= sd]
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            communications = [c for c in communications if c.comm_at <= ed]
        except ValueError:
            pass
    if comm_ids:
        comm_id_set = set(comm_ids)
        communications = [c for c in communications if c.id in comm_id_set]

    contact_ids = set()
    for c in communications:
        for cc in c.communication_contacts:
            contact_ids.add(cc.contact_id)
    contact_map = {}
    if contact_ids:
        for ct in db.query(Contact).filter(Contact.id.in_(contact_ids)).all():
            contact_map[ct.id] = ct

    task_contacts = task.contacts or []
    tag_names = [tag_info[tid].name for tid in tag_ids if tid in tag_info]

    comm_list = []
    for c in communications:
        comm_contacts = []
        for cc in c.communication_contacts:
            ct = contact_map.get(cc.contact_id)
            if ct:
                comm_contacts.append(ct.name)

        att_list = []
        for att in (c.attachments or []):
            full_path = os.path.join(UPLOAD_DIR, proj.display_id, task.display_id, f'comm_{c.id}', att.filename)
            ext = os.path.splitext(att.original_filename)[1].lower()
            att_list.append({
                'id': att.id,
                'original_filename': att.original_filename,
                'file_size': att.file_size,
                'is_image': ext in IMAGE_EXTENSIONS,
                'full_path': full_path if os.path.isfile(full_path) else None,
            })

        old_status_name = status_pool[c.old_status_id].name if c.old_status_id and c.old_status_id in status_pool else ''
        new_status_name = status_pool[c.new_status_id].name if c.new_status_id and c.new_status_id in status_pool else ''

        comm_list.append({
            'id': c.id,
            'comm_at': c.comm_at,
            'comm_type': c.comm_type,
            'content': c.content,
            'contacts': comm_contacts,
            'old_status_id': c.old_status_id,
            'new_status_id': c.new_status_id,
            'old_status_name': old_status_name,
            'new_status_name': new_status_name,
            'attachments': att_list,
        })

    task_attrs = {
        'title': task.title,
        'display_id': task.display_id,
        'status': status_pool[task.status_id].name if task.status_id and task.status_id in status_pool else '',
        'priority': PRIORITY_LABELS.get(task.priority, task.priority),
        'due_date': task.due_date.strftime('%Y-%m-%d') if task.due_date else '未设置',
        'description': task.description or '暂无描述',
        'created_at': task.created_at.strftime('%Y-%m-%d %H:%M') if task.created_at else '',
        'updated_at': task.updated_at.strftime('%Y-%m-%d %H:%M') if task.updated_at else '',
        'contacts': ', '.join([ct.name for ct in task_contacts]) if task_contacts else '无',
        'tags': ', '.join(tag_names) if tag_names else '无',
    }

    return {
        'project_name': project_info.name if project_info else '',
        'project_display_id': proj.display_id,
        'task_attrs': task_attrs,
        'communications': comm_list,
    }


def _add_task_info_table(doc: Document, task_attrs: dict, selected_fields: List[str]):
    """添加任务基本信息（表格）"""
    doc.add_heading('一、任务基本信息', level=1)

    field_order = ['title', 'display_id', 'status', 'priority', 'due_date',
                   'description', 'contacts', 'tags', 'created_at', 'updated_at']
    field_labels = {
        'title': '任务名称', 'display_id': '显示ID', 'status': '状态',
        'priority': '优先级', 'due_date': '截止日期', 'description': '描述',
        'contacts': '对接人', 'tags': '标签', 'created_at': '创建时间', 'updated_at': '更新时间'
    }

    items = [(field_labels[k], task_attrs[k]) for k in field_order
             if k in selected_fields and k in task_attrs]

    if not items:
        return

    table = doc.add_table(rows=len(items), cols=2)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # 表宽占满页面
    section = doc.sections[0]
    usable = section.page_width - section.left_margin - section.right_margin
    twips = int(usable * 1440 / 914400)
    tblPr = table._tbl.find(qn('w:tblPr'))
    if tblPr is None:
        tblPr = OxmlElement('w:tblPr')
        table._tbl.insert(0, tblPr)
    tblW = OxmlElement('w:tblW')
    tblW.set(qn('w:w'), str(twips))
    tblW.set(qn('w:type'), 'dxa')
    tblPr.append(tblW)

    for i, (label, value) in enumerate(items):
        cell_label = table.rows[i].cells[0]
        cell_label.width = Cm(3)
        _set_cell_shading(cell_label, 'F2F2F2')
        _add_run(cell_label.paragraphs[0], label, size=BODY_SIZE, bold=True,
                 font_name=FONT_FAMILY_HEADING)
        cell_value = table.rows[i].cells[1]
        _add_run(cell_value.paragraphs[0], value, size=BODY_SIZE)

    doc.add_paragraph()


def _format_size(bytes_val: int) -> str:
    if bytes_val > 1024 * 1024:
        return f'{bytes_val / 1024 / 1024:.1f}MB'
    elif bytes_val > 1024:
        return f'{bytes_val / 1024:.1f}KB'
    return f'{bytes_val}B'


def generate_export_package(
    db: Session,
    project_id: str,
    task_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fields: Optional[List[str]] = None,
    comm_ids: Optional[List[int]] = None,
) -> bytes:
    """
    生成导出包（ZIP 文件），内含：
    1. DOCX 说明文档（含内嵌图片）
    2. attachments/{记录序号}/ 目录（每个沟通记录的附件各自放在对应编号的文件夹）
    """
    all_field_keys = list(TASK_ATTR_OPTIONS.keys())
    selected_fields = fields if fields else all_field_keys

    data = build_export_data(db, project_id, task_id, start_date, end_date, selected_fields, comm_ids)
    task_attrs = data['task_attrs']
    communications = data['communications']
    project_name = data['project_name']
    project_display_id = data['project_display_id']

    # ======================== 生成 DOCX ========================
    doc = Document()

    # 设置默认样式
    style = doc.styles['Normal']
    style.font.name = FONT_FAMILY
    style.font.size = BODY_SIZE
    style.element.rPr.rFonts.set(qn('w:eastAsia'), FONT_FAMILY)
    # Normal 段落间距
    pPr = style.element.get_or_add_pPr()
    pSpacing = OxmlElement('w:spacing')
    pSpacing.set(qn('w:line'), '360')
    pSpacing.set(qn('w:lineRule'), 'auto')
    pPr.append(pSpacing)

    # 设置标题样式
    _set_heading_style(doc, 1, FONT_FAMILY_HEADING, HEADING1_SIZE)
    _set_heading_style(doc, 2, FONT_FAMILY_HEADING, HEADING2_SIZE)

    # ---- 封面 ----
    for _ in range(6):
        _new_paragraph(doc, '', size=BODY_SIZE, alignment=WD_ALIGN_PARAGRAPH.CENTER)

    _new_paragraph(doc, '任务说明文档', size=TITLE_SIZE, bold=True,
                   font_name=FONT_FAMILY_HEADING, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                   before=200, after=100)
    _new_paragraph(doc, task_attrs.get('title', ''), size=SUBTITLE_SIZE,
                   font_name=FONT_FAMILY_HEADING, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                   before=100, after=200)
    _new_paragraph(doc, '', size=BODY_SIZE)
    _new_paragraph(doc, f'项目名称：{project_name}（{project_display_id}）', size=SMALL_SIZE,
                   alignment=WD_ALIGN_PARAGRAPH.CENTER)
    _new_paragraph(doc, f'导出日期：{datetime.now().strftime("%Y年%m月%d日")}', size=SMALL_SIZE,
                   alignment=WD_ALIGN_PARAGRAPH.CENTER)

    doc.add_page_break()

    # ---- 正文：任务基本信息 ----
    _add_task_info_table(doc, task_attrs, selected_fields)
    doc.add_page_break()

    # ---- 正文：沟通记录 ----
    doc.add_heading('二、沟通记录', level=1)
    _new_paragraph(doc, f'共 {len(communications)} 条记录，按时间先后顺序排列。', size=SMALL_SIZE)

    for idx, comm in enumerate(communications):
        record_num = idx + 1
        comm_time = comm['comm_at'].strftime('%Y-%m-%d %H:%M') if comm['comm_at'] else '未知时间'

        doc.add_heading(f'（{record_num}）{comm_time} 记录', level=2)

        # 元信息：时间 · 类型 · 对接人
        meta_parts = [f'沟通时间：{comm_time}']
        if comm['comm_type']:
            meta_parts.append(comm['comm_type'])
        contact_text = '、'.join(comm['contacts']) if comm['contacts'] else ''
        if contact_text:
            meta_parts.append(f'对接人：{contact_text}')
        _new_paragraph(doc, ' | '.join(meta_parts), size=SMALL_SIZE)

        # 状态变更
        if comm['old_status_id'] or comm['new_status_id']:
            if comm['old_status_name'] and comm['new_status_name']:
                status_line = f'状态变更：{comm["old_status_name"]} → {comm["new_status_name"]}'
            elif comm['new_status_name']:
                status_line = f'状态变更为：{comm["new_status_name"]}'
            else:
                status_line = f'状态：{comm["old_status_name"]}（不变）'
            _new_paragraph(doc, status_line, size=SMALL_SIZE)

        # 沟通内容
        _new_paragraph(doc, '沟通内容：', size=BODY_SIZE, bold=True, before=80)
        if comm['content']:
            lines = comm['content'].split('\n')
            for line in lines:
                if line.strip():
                    _new_paragraph(doc, line.strip(), size=BODY_SIZE, first_line_indent=480)

        # ---- 附件 ----
        image_atts = [a for a in comm['attachments'] if a['is_image']]
        non_image_atts = [a for a in comm['attachments'] if not a['is_image']]

        # 非图片附件
        if non_image_atts:
            _new_paragraph(doc, '附件：', size=BODY_SIZE, bold=True, before=120)
            for att in non_image_atts:
                size_str = _format_size(att['file_size'])
                p = _new_paragraph(doc, '', size=BODY_SIZE, before=20, first_line_indent=480)
                if att['full_path']:
                    rel_path = f'attachments/{record_num}/{att["original_filename"]}'
                    _add_hyperlink(p, att['original_filename'], rel_path, size=BODY_SIZE)
                else:
                    _add_run(p, att['original_filename'], size=BODY_SIZE)
                _add_run(p, f'（{size_str}）', size=BODY_SIZE)

        # 内嵌图片
        if image_atts:
            _new_paragraph(doc, '【图片附件】', size=BODY_SIZE, bold=True, before=120)
            for att in image_atts:
                if att['full_path']:
                    try:
                        pic_p = _new_paragraph(doc, '', alignment=WD_ALIGN_PARAGRAPH.CENTER,
                                               before=80, after=40)
                        pic_p.add_run().add_picture(att['full_path'], width=Inches(5.0))
                        cap_p = _new_paragraph(doc, '', alignment=WD_ALIGN_PARAGRAPH.CENTER, before=20)
                        rel_path = f'attachments/{record_num}/{att["original_filename"]}'
                        _add_hyperlink(cap_p, att['original_filename'], rel_path, size=SMALL_SIZE)
                    except Exception:
                        _new_paragraph(doc, f'　　[图片加载失败：{att["original_filename"]}]',
                                       size=BODY_SIZE, color=RGBColor(180, 0, 0))
                else:
                    _new_paragraph(doc, f'　　[文件不可访问：{att["original_filename"]}]',
                                   size=BODY_SIZE, color=RGBColor(180, 0, 0))

        # 分隔线
        if idx < len(communications) - 1:
            _new_paragraph(doc, '', before=200)

    # ---- 保存 DOCX ----
    docx_buffer = io.BytesIO()
    doc.save(docx_buffer)
    docx_bytes = docx_buffer.getvalue()

    # ======================== 生成 ZIP ========================
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f'{task_attrs["title"]}_说明文档.docx', docx_bytes)

        att_count = 0
        for rec_idx, comm in enumerate(communications):
            record_number = rec_idx + 1
            for att in comm['attachments']:
                if att['full_path']:
                    try:
                        arcname = f'attachments/{record_number}/{att["original_filename"]}'
                        zf.write(att['full_path'], arcname)
                        att_count += 1
                    except Exception:
                        pass

    return zip_buffer.getvalue(), len(communications), att_count
