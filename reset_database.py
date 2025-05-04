import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import engine, async_session_maker
from app.db.models import Device
from app.db.lifespan import seed_initial_data


async def reset_database():
    print("正在刪除現有數據...")
    async with engine.begin() as conn:
        await conn.run_sync(lambda conn: conn.execute("DELETE FROM device"))

    print("開始重新插入初始設備數據...")
    async with async_session_maker() as session:
        await seed_initial_data(session)

    print("數據庫重置完成")


if __name__ == "__main__":
    asyncio.run(reset_database())
