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

logger = logging.getLogger(__name__)


async def create_db_and_tables():
    """Creates database tables if they don't exist."""
    async with engine.begin() as conn:
        logger.info("Creating database tables...")
        # Use run_sync for SQLModel metadata operations with async engine
        await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("Database tables created (if they didn't exist).")


# async def seed_initial_data(session: AsyncSession):
#     """Inserts initial device data if the database is empty."""
#     logger.info("Checking if initial data seeding is needed...")
#     # Check if any devices exist - more reliable count
#     result = await session.execute(select(count(Device.id)))
#     device_count = result.scalar_one_or_none() or 0

#     if device_count > 0:
#         logger.info(
#             f"Database already contains {device_count} devices. Skipping seeding."
#         )
#         return

#     logger.info("Seeding initial device data...")

#     try:
#         # Create base devices first with x, y, z coordinates
#         tx_main_dev = Device(
#             name="tx_main",
#             role=DeviceRole.DESIRED,
#             x=0.0,  # longitude
#             y=60.0,  # latitude
#             z=2.0,  # altitude
#             active=True,
#         )
#         tx_i_dev = Device(
#             name="tx_i",
#             role=DeviceRole.JAMMER,
#             x=-100.0,
#             y=100.0,
#             z=2.0,
#             active=True,
#         )
#         rx_dev = Device(
#             name="rx", role=DeviceRole.RECEIVER, x=0.0, y=0.0, z=1.5, active=True
#         )
#         session.add_all([tx_main_dev, tx_i_dev, rx_dev])
#         await session.flush()  # Flush to get IDs before creating related records

#         # 不再需要創建額外的 Transmitter/Receiver 記錄，因為現在使用單一 Device 模型
#         await session.commit()
#         logger.info("Initial device data seeded successfully.")

#     except Exception as e:
#         logger.error(f"Error seeding initial data: {e}", exc_info=True)
#         await session.rollback()  # Rollback on error


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
    # async with async_session_maker() as session:
    #     await seed_initial_data(session)
    # logger.info("Database initialization complete.")
    yield
    logger.info("Application shutdown.")
    # Add any other cleanup logic here if needed
