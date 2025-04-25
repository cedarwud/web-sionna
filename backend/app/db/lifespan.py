import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import SQLModel, select
from sqlalchemy.sql.functions import count
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import engine, async_session_maker
from app.db.models import Device, Transmitter, Receiver, DeviceType, TransmitterType # Import necessary models
from app.core.config import OUTPUT_DIR, configure_gpu_cpu, configure_matplotlib # Import config functions
import os

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
        logger.info(f"Database already contains {device_count} devices. Skipping seeding.")
        return

    logger.info("Seeding initial device data...")
    # Define initial devices
    # Note: ST_MakePointZ might need casting, ST_GeomFromText is often safer cross-platform
    # Using ST_GeomFromText as in the previous SQL example
    from geoalchemy2.functions import ST_GeomFromText

    try:
        # Create base devices first
        tx_main_dev = Device(
            name="tx_main",
            device_type=DeviceType.TRANSMITTER,
            position=ST_GeomFromText('POINT Z (0 60 2)', 4326),
            active=True
        )
        tx_i_dev = Device(
            name="tx_i",
            device_type=DeviceType.TRANSMITTER,
            position=ST_GeomFromText('POINT Z (-100 100 2)', 4326),
            active=True
        )
        rx_dev = Device(
            name="rx",
            device_type=DeviceType.RECEIVER,
            position=ST_GeomFromText('POINT Z (0 0 1.5)', 4326),
            active=True
        )
        session.add_all([tx_main_dev, tx_i_dev, rx_dev])
        await session.flush() # Flush to get IDs before creating related records

        # Create Transmitter/Receiver specific records using the generated IDs
        if tx_main_dev.id and tx_i_dev.id and rx_dev.id:
            tx_main = Transmitter(id=tx_main_dev.id, transmitter_type=TransmitterType.SIGNAL)
            tx_i = Transmitter(id=tx_i_dev.id, transmitter_type=TransmitterType.INTERFERER)
            rx = Receiver(id=rx_dev.id)
            session.add_all([tx_main, tx_i, rx])
            await session.commit()
            logger.info("Initial device data seeded successfully.")
        else:
             logger.error("Failed to retrieve generated IDs for devices. Rolling back seed.")
             await session.rollback()

    except Exception as e:
        logger.error(f"Error seeding initial data: {e}", exc_info=True)
        await session.rollback() # Rollback on error

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