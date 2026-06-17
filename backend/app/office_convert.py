"""Office 文档转 PDF — 使用 Microsoft Office COM 自动化

注意：pywin32 是可选依赖。未安装时，转换功能静默返回 None，
不影响应用其他功能。
"""

import os

# pywin32 可选加载
try:
    import pythoncom
    import win32com.client
    from win32com.client import constants
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False


OFFICE_EXTS = {'.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'}


def is_office_file(file_path: str) -> bool:
    _, ext = os.path.splitext(file_path)
    return ext.lower() in OFFICE_EXTS


def convert_to_pdf(input_path: str, output_dir: str) -> str | None:
    """将 Office 文档转换为 PDF，返回 PDF 路径；失败或不可用时返回 None。"""
    if not PYWIN32_AVAILABLE:
        print("[office_convert] pywin32 未安装，跳过 Office 转换")
        return None

    name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{name}.pdf")

    # 已有缓存
    if os.path.exists(output_path):
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
