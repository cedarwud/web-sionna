"""
該腳本重置資料庫中的設備數據
- 刪除所有現有設備
- 插入預定義的發射器和接收器
"""

import sqlite3
import os
import numpy as np

# 資料庫檔案路徑，請根據實際情況調整
DB_PATH = "backend/app.db"  # 預設SQLite資料庫路徑


def reset_database():
    # 確認資料庫檔案存在
    if not os.path.exists(DB_PATH):
        print(f"錯誤：找不到資料庫檔案 {DB_PATH}")
        return False

    # 連接資料庫
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 刪除所有現有設備
        print("刪除所有現有設備...")
        cursor.execute("DELETE FROM device")

        # 定義要插入的設備
        tx_list = [
            ("tx0", -100, -100, 20, np.pi * 5 / 6, 0, 0, "desired", 30, True),
            ("tx1", -100, 50, 20, np.pi / 6, 0, 0, "desired", 30, True),
            ("tx2", 100, -100, 20, -np.pi / 2, 0, 0, "desired", 30, True),
            ("jam1", 100, 50, 20, np.pi / 2, 0, 0, "jammer", 40, True),
            ("jam2", 50, 50, 20, np.pi / 2, 0, 0, "jammer", 40, True),
            ("jam3", -50, -50, 20, np.pi / 2, 0, 0, "jammer", 40, True),
        ]

        rx_data = ("rx", 0, 0, 20, 0, 0, 0, "receiver", 0, True)

        # 插入數據的SQL語句
        insert_sql = """
        INSERT INTO device (name, position_x, position_y, position_z, orientation_x, orientation_y, orientation_z, role, power_dbm, active) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # 插入發射器
        print("插入發射器數據...")
        for tx in tx_list:
            cursor.execute(insert_sql, tx)

        # 插入接收器
        print("插入接收器數據...")
        cursor.execute(insert_sql, rx_data)

        # 提交所有更改
        conn.commit()
        print(f"成功重置資料庫！插入了 {len(tx_list) + 1} 個設備")
        return True

    except Exception as e:
        print(f"重置資料庫時發生錯誤: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    reset_database()
