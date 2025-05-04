import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import SQLModel, select
from sqlalchemy.sql.functions import count
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import engine, async_session_maker
from app.db.models import Device, DeviceRole  # Import necessary models
from app.core.config import (
    OUTPUT_DIR,
    configure_gpu_cpu,
    configure_matplotlib,
)  # Import config functions
import os
import numpy as np

logger = logging.getLogger(__name__)


async def create_db_and_tables():
    """Creates database tables if they don't exist."""
    async with engine.begin() as conn:
        logger.info("Creating database tables...")
        # Use run_sync for SQLModel metadata operations with async engine
        await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("Database tables created (if they didn't exist).")


async def seed_initial_data(session: AsyncSession):
    """Inserts initial device data if the database is empty."""
    logger.info("Checking if initial data seeding is needed...")
    # Check if any devices exist - more reliable count
    result = await session.execute(select(count(Device.id)))
    device_count = result.scalar_one_or_none() or 0

    if device_count > 0:
        logger.info(
            f"Database already contains {device_count} devices. Skipping seeding."
        )
        return

    logger.info("Seeding initial device data...")

    try:
        # 指定的發射器設備列表
        tx_list = [
            ("tx0", [-100, -100, 0], [np.pi * 5 / 6, 0, 0], "desired", 30),
            ("tx1", [-100, 50, 0], [np.pi / 6, 0, 0], "desired", 30),
            ("tx2", [100, -100, 0], [-np.pi / 2, 0, 0], "desired", 30),
            ("jam1", [100, 50, 0], [np.pi / 2, 0, 0], "jammer", 40),
            ("jam2", [50, 50, 0], [np.pi / 2, 0, 0], "jammer", 40),
            ("jam3", [-50, -50, 0], [np.pi / 2, 0, 0], "jammer", 40),
        ]

        # 指定的接收器設備
        rx_config = ("rx", [0, 0, 50], [0, 0, 0], "receiver", 0)

        # 創建發射器設備
        devices_to_add = []
        for tx_name, position, orientation, role, power_dbm in tx_list:
            device = Device(
                name=tx_name,
                position_x=position[0],
                position_y=position[1],
                position_z=position[2],
                orientation_x=orientation[0],
                orientation_y=orientation[1],
                orientation_z=orientation[2],
                role=role,
                power_dbm=power_dbm,
                active=True,
            )
            devices_to_add.append(device)

        # 創建接收器設備
        rx_name, rx_position, rx_orientation, rx_role, rx_power_dbm = rx_config
        rx_device = Device(
            name=rx_name,
            position_x=rx_position[0],
            position_y=rx_position[1],
            position_z=rx_position[2],
            orientation_x=rx_orientation[0],
            orientation_y=rx_orientation[1],
            orientation_z=rx_orientation[2],
            role=rx_role,
            power_dbm=rx_power_dbm,
            active=True,
        )
        devices_to_add.append(rx_device)

        # 添加所有設備到數據庫
        session.add_all(devices_to_add)
        await session.commit()
        logger.info(f"成功初始化 {len(devices_to_add)} 個設備到數據庫")

    except Exception as e:
        logger.error(f"Error seeding initial data: {e}", exc_info=True)
        await session.rollback()  # Rollback on error


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager for FastAPI startup and shutdown logic."""
    logger.info("Application startup: Configuring environment...")
    # Configure GPU/CPU and Matplotlib on startup
    configure_gpu_cpu()
    configure_matplotlib()
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.info("Initializing database...")
    await create_db_and_tables()
    # Seed data only if tables are empty
    async with async_session_maker() as session:
        await seed_initial_data(session)
    logger.info("Database initialization complete.")
    yield
    logger.info("Application shutdown.")
    # Add any other cleanup logic here if needed
