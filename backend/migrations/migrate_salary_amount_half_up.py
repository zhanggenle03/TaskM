"""
一次性修正脚本：salary_items 中「基数×比例」金额的四舍五入口径统一为 half-up（与前端 round2 一致）。

背景：前端 round2 = Math.round((n + Number.EPSILON) * 100) / 100，对 33.635 → 33.64（half-up）；
后端旧 _item_amount 用 Python 内置 round（银行家舍入 + 浮点表示误差），对 33.635 → 33.63，
导致明细展开显示的存库金额（33.63）与编辑/配置预览（33.64）不一致。

本脚本只修正 base 与 rate 均非空的存量行（amount 按 half-up 重算），幂等可重复执行；
运行前会自动做一致性备份（taskm.db.bak_amount_half_up，含 WAL 内容）。
"""
import os
import sqlite3
import sys
from decimal import Decimal, ROUND_HALF_UP

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "taskm.db"))


def round2_half_up(v):
    return float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def main():
    if not os.path.exists(DB_PATH):
        print(f"数据库不存在: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    try:
        backup_path = DB_PATH + ".bak_amount_half_up"
        conn.backup(sqlite3.connect(backup_path))
        print(f"已备份数据库 -> {backup_path}")

        rows = conn.execute(
            "SELECT id, base, rate, amount FROM salary_items WHERE base IS NOT NULL AND rate IS NOT NULL"
        ).fetchall()
        updated = []
        for rid, base, rate, amount in rows:
            new_amt = round2_half_up(base * rate / 100.0)
            if abs(new_amt - amount) > 1e-9:
                updated.append((rid, amount, new_amt))
        if not updated:
            print("无需修正：所有 base/rate 行的 amount 均与 half-up 计算一致。")
            return
        conn.executemany(
            "UPDATE salary_items SET amount = ? WHERE id = ?",
            [(a, rid) for rid, _, a in updated],
        )
        conn.commit()
        print(f"已修正 {len(updated)} 条记录：")
        for rid, old, new in updated:
            print(f"  id={rid}: {old} -> {new}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
