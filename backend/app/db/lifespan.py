import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Ensure SQLModel specific imports are correctly managed if you mix ORMs
from sqlmodel import (
    SQLModel,
    select as sqlmodel_select,
)  # SQLModel used for Device model
from sqlalchemy.sql.functions import count
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sqlalchemy_select  # For SQLAlchemy models

from app.db.base import engine, async_session_maker

# 更新為領域驅動設計後的模型導入
from app.domains.device.models.device_model import Device, DeviceRole  # 從領域模型導入

from app.core.config import (
    OUTPUT_DIR,
    configure_gpu_cpu,
    configure_matplotlib,
)
import os

logger = logging.getLogger(__name__)


async def create_db_and_tables():
    """Creates database tables if they don't exist."""
    async with engine.begin() as conn:
        logger.info("Creating database tables...")
        # This will create tables for all models registered with SQLModel.metadata
        from app.db.base_class import Base as SQLAlchemyBase

        await conn.run_sync(
            SQLAlchemyBase.metadata.create_all
        )  # Creates database tables
        await conn.run_sync(
            SQLModel.metadata.create_all
        )  # Creates Device table (and any other SQLModels)
        logger.info("Database tables created (if they didn't exist).")


async def seed_initial_device_data(session: AsyncSession):
    """Inserts initial device data if minimum roles (TX, RX, JAM) are not met."""
    logger.info("Checking if initial data seeding is needed for Devices...")

    query_desired = sqlmodel_select(count(Device.id)).where(
        Device.active == True, Device.role == DeviceRole.DESIRED
    )
    query_receiver = sqlmodel_select(count(Device.id)).where(
        Device.active == True, Device.role == DeviceRole.RECEIVER
    )
    query_jammer = sqlmodel_select(count(Device.id)).where(
        Device.active == True, Device.role == DeviceRole.JAMMER
    )

    result_desired = await session.execute(query_desired)
    result_receiver = await session.execute(query_receiver)
    result_jammer = await session.execute(query_jammer)

    desired_count = result_desired.scalar_one_or_none() or 0
    receiver_count = result_receiver.scalar_one_or_none() or 0
    jammer_count = result_jammer.scalar_one_or_none() or 0

    if desired_count > 0 and receiver_count > 0 and jammer_count > 0:
        logger.info(
            f"Device Database already contains active TX ({desired_count}), RX ({receiver_count}), Jammer ({jammer_count}). Skipping Device seeding."
        )
        return

    logger.info(
        f"Minimum Device role requirement not met. Seeding initial Device data..."
    )

    initial_devices = [
        # Desired Transmitters (基站)
        Device(
            name="BS_001",
            position_x=10.0,
            position_y=10.0,
            position_z=20.0,
            orientation_x=0.0,
            orientation_y=0.0,
            orientation_z=0.0,
            role=DeviceRole.DESIRED,
            power_dbm=30.0,
            active=True,
        ),
        Device(
            name="BS_002",
            position_x=-15.0,
            position_y=25.0,
            position_z=18.0,
            orientation_x=0.0,
            orientation_y=0.0,
            orientation_z=0.0,
            role=DeviceRole.DESIRED,
            power_dbm=28.5,
            active=True,
        ),
        Device(
            name="BS_003",
            position_x=30.0,
            position_y=-10.0,
            position_z=22.0,
            orientation_x=0.0,
            orientation_y=0.0,
            orientation_z=0.0,
            role=DeviceRole.DESIRED,
            power_dbm=32.0,
            active=True,
        ),
        # Receivers (用戶設備)
        Device(
            name="UE_001",
            position_x=5.0,
            position_y=5.0,
            position_z=1.5,
            orientation_x=0.0,
            orientation_y=0.0,
            orientation_z=0.0,
            role=DeviceRole.RECEIVER,
            power_dbm=0.0,  # 接收器通常不需要發送功率
            active=True,
        ),
        Device(
            name="UE_002",
            position_x=-8.0,
            position_y=12.0,
            position_z=1.5,
            orientation_x=0.0,
            orientation_y=0.0,
            orientation_z=0.0,
            role=DeviceRole.RECEIVER,
            power_dbm=0.0,
            active=True,
        ),
        # Jammers (干擾器)
        Device(
            name="JAM_001",
            position_x=0.0,
            position_y=0.0,
            position_z=15.0,
            orientation_x=0.0,
            orientation_y=0.0,
            orientation_z=0.0,
            role=DeviceRole.JAMMER,
            power_dbm=25.0,
            active=True,
        ),
        Device(
            name="JAM_002",
            position_x=20.0,
            position_y=20.0,
            position_z=12.0,
            orientation_x=0.0,
            orientation_y=0.0,
            orientation_z=0.0,
            role=DeviceRole.JAMMER,
            power_dbm=23.0,
            active=True,
        ),
        Device(
            name="JAM_003",
            position_x=-25.0,
            position_y=-15.0,
            position_z=18.0,
            orientation_x=0.0,
            orientation_y=0.0,
            orientation_z=0.0,
            role=DeviceRole.JAMMER,
            power_dbm=27.0,
            active=True,
        ),
    ]

    for device in initial_devices:
        session.add(device)

    await session.commit()
    logger.info("Initial Device data seeded successfully.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager for FastAPI startup and shutdown logic."""
    logger.info("Application startup sequence initiated...")
    configure_gpu_cpu()
    configure_matplotlib()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.info("Environment configured.")

    logger.info("Database initialization sequence...")
    await create_db_and_tables()

    # 異步初始化資料庫
    async with async_session_maker() as db_session:
        # 初始化設備資料
        await seed_initial_device_data(db_session)

    logger.info("Application startup complete.")

    yield

    # 應用程式關閉時執行清理
    logger.info("Application shutdown complete.")
