"""
迁移脚本：给数据库中所有 <blockquote> 缺失 data-bq-border 的补上边框色。
背景色→边框色映射与前端 BQ_PRESETS 保持一致。
"""
import re
import sqlite3
import os

# 背景色→边框色映射（与 frontend BQ_PRESETS 一致）
BQ_BORDER_MAP = {
    '#f8f8f8': '#ccc',
    '#e8f4fd': '#9fc5e8',
    '#e8f8e8': '#9fc89f',
    '#fef9e7': '#e6d88a',
    '#fde8e8': '#e89f9f',
}


def fix_blockquote_border(html: str) -> str:
    """给 <blockquote data-bq-color="..."> 缺失 data-bq-border 的补上边框色"""
    def repl(m):
        full = m.group(0)
        if 'data-bq-border=' in full:
            return full
        color_m = re.search(r'data-bq-color=["\']([^"\']+)', full, re.IGNORECASE)
        if not color_m:
            return full
        color = color_m.group(1)
        border = BQ_BORDER_MAP.get(color.lower(), color)
        return full[:-1].rstrip() + f' data-bq-border="{border}">'
    return re.sub(r'<blockquote[^>]*>', repl, html, flags=re.IGNORECASE)


def main():
    db_path = os.path.join(os.path.dirname(__file__), 'taskm.db')
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, description FROM requirements WHERE description LIKE '%blockquote%'")
    total_fixed = 0
    for rid, desc in cur.fetchall():
        new_desc = fix_blockquote_border(desc)
        if new_desc != desc:
            cur.execute('UPDATE requirements SET description = ? WHERE id = ?', (new_desc, rid))
            total_fixed += 1
            print(f'修复 ID={rid}')
    conn.commit()
    print(f'共修复 {total_fixed} 条记录')


if __name__ == '__main__':
    main()
