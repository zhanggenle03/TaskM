"""
迁移脚本：为 salary_items 表添加「缴费基数×比例」字段
- base  REAL                             缴费基数（基数×比例自动算时用；可空）
- rate  REAL                             比例（百分比，如 8 表示 8%；与 base 同时非空时 amount=base*rate/100）

仅对「已存在 salary_items 表」的旧库执行；全新库由 Base.metadata.create_all 在建表时直接带出这两列。
幂等：列已存在则跳过。也可由 app.main 启动时通过 ensure_salary_item_columns(engine) 自动执行。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, ensure_salary_item_columns


def main():
    ensure_salary_item_columns(engine)
    print("\n薪资 base/rate 字段迁移完成！")


if __name__ == "__main__":
    main()
