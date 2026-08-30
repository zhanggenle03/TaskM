"""Office 文档转 PDF — 使用 Microsoft Office COM 自动化

注意：pywin32 是可选依赖。未安装时，转换功能静默返回 None，
不影响应用其他功能。
"""

import os

# pywin32 可选加载
try:
    import pythoncom
    import win32com.client
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False


OFFICE_EXTS = {'.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'}


def is_office_file(file_path: str) -> bool:
    _, ext = os.path.splitext(file_path)
    return ext.lower() in OFFICE_EXTS


def remove_attachment_files(file_path: str) -> None:
    """删除附件源文件，并清理其 Office 转换缓存 PDF（仅当源文件为 Office 文档时才有同名 .pdf 缓存）。

    转换缓存在源文件同目录（{name}.pdf），删除附件时若不清理会残留孤儿文件。
    源文件本身是 .pdf 时 is_office_file 为 False，不会误删。
    """
    if not file_path or not os.path.isfile(file_path):
        return
    try:
        os.remove(file_path)
    except OSError:
        return
    if is_office_file(file_path):
        pdf_cache = os.path.splitext(file_path)[0] + ".pdf"
        if os.path.isfile(pdf_cache):
            try:
                os.remove(pdf_cache)
            except OSError:
                pass


def convert_to_pdf(input_path: str, output_dir: str) -> str | None:
    """将 Office 文档转换为 PDF，返回 PDF 路径；失败或不可用时返回 None。"""
    if not PYWIN32_AVAILABLE:
        print("[office_convert] pywin32 未安装，跳过 Office 转换")
        return None

    name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{name}.pdf")

    # 缓存判定：源文件未在缓存生成后修改过则复用；
    # 用户用系统程序（Word/Excel 等）编辑保存后源文件 mtime 更新 → 删旧缓存重新转换
    if os.path.exists(output_path):
        try:
            if os.path.getmtime(input_path) <= os.path.getmtime(output_path):
                return output_path
        except OSError:
            return output_path
        try:
            os.remove(output_path)
        except OSError:
            return output_path

    ext = os.path.splitext(input_path)[1].lower()
    pythoncom.CoInitialize()
    app = None
    try:
        if ext in ('.doc', '.docx'):
            app = win32com.client.Dispatch("Word.Application")
            app.Visible = False
            doc = app.Documents.Open(os.path.abspath(input_path))
            doc.SaveAs(os.path.abspath(output_path), FileFormat=17)  # wdFormatPDF
            doc.Close()
        elif ext in ('.xls', '.xlsx'):
            app = win32com.client.Dispatch("Excel.Application")
            app.Visible = False
            wb = app.Workbooks.Open(os.path.abspath(input_path))
            wb.ExportAsFixedFormat(0, os.path.abspath(output_path))  # xlTypePDF
            wb.Close()
        elif ext in ('.ppt', '.pptx'):
            app = win32com.client.Dispatch("PowerPoint.Application")
            app.Visible = False
            prs = app.Presentations.Open(os.path.abspath(input_path))
            prs.SaveAs(os.path.abspath(output_path), 32)  # ppSaveAsPDF
            prs.Close()
        else:
            return None
        return output_path if os.path.exists(output_path) else None
    except Exception as e:
        print(f"[office_convert] 转换失败: {e}")
        return None
    finally:
        if app:
            try:
                app.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()
