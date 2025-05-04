#!/usr/bin/env python
"""
數據庫遷移腳本
此腳本用於升級數據庫表結構，添加和重命名欄位
"""
import asyncio
from sqlalchemy import text
from app.db.base import engine


async def migrate_db():
    # 建立連接
    print("開始遷移數據庫結構...")
    try:
        async with engine.begin() as conn:
            # 1. 檢查是否已經存在新欄位
            check_sql = """
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'device' AND column_name = 'position_x'
            """
            result = await conn.execute(text(check_sql))
            exists = result.fetchone()

            if exists:
                print("數據庫結構已經是最新的，無需遷移")
                return

            # 2. 添加新欄位
            print("添加新欄位...")
            await conn.execute(
                text(
                    """
            ALTER TABLE device
            ADD COLUMN position_x INTEGER,
            ADD COLUMN position_y INTEGER,
            ADD COLUMN position_z INTEGER,
            ADD COLUMN orientation_x FLOAT DEFAULT 0.0,
            ADD COLUMN orientation_y FLOAT DEFAULT 0.0,
            ADD COLUMN orientation_z FLOAT DEFAULT 0.0,
            ADD COLUMN power_dbm INTEGER DEFAULT 0
            """
                )
            )

            # 3. 複製數據：將現有數據從舊欄位複製到新欄位
            print("複製數據...")
            await conn.execute(
                text(
                    """
            UPDATE device
            SET position_x = x,
                position_y = y,
                position_z = z,
                orientation_x = orientation,
                power_dbm = power
            """
                )
            )

            # 4. 移除舊欄位
            print("移除舊欄位...")
            await conn.execute(
                text(
                    """
            ALTER TABLE device
            DROP COLUMN x,
            DROP COLUMN y,
            DROP COLUMN z,
            DROP COLUMN orientation,
            DROP COLUMN power
            """
                )
            )

            print("數據庫遷移完成！")

    except Exception as e:
        print(f"遷移過程出錯: {e}")


if __name__ == "__main__":
    asyncio.run(migrate_db())
