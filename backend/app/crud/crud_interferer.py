# backend/app/crud/crud_interferer.py
import logging
from typing import List, Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from geoalchemy2.functions import ST_GeomFromText, ST_AsText # 引入 PostGIS 函數

from app.db.models import Device, Transmitter, DeviceType, TransmitterType # 引用 DB 模型
from app.schemas.interferer import InterfererCreate, InterfererUpdate # 引用 Schemas

logger = logging.getLogger(__name__)

# --- Helper to create WKT string ---
def create_point_wkt(lon: float, lat: float, alt: float) -> str:
    # 使用 SRID 4326 (WGS 84)
    return f'SRID=4326;POINT Z ({lon} {lat} {alt})'

# --- Create Interferer ---
async def create_interferer(db: AsyncSession, *, obj_in: InterfererCreate) -> Device:
    """
    創建一個新的干擾源設備和對應的發射器記錄。
    """
    logger.info(f"Attempting to create interferer: {obj_in.name}")
    try:
        # 1. 創建 Device 記錄
        position_wkt = create_point_wkt(*obj_in.position)
        db_device = Device(
            name=obj_in.name,
            device_type=DeviceType.TRANSMITTER, # 固定為 TRANSMITTER
            position=position_wkt, # 使用 WKT 字串
            active=obj_in.active
        )
        db.add(db_device)
        await db.flush() # 刷新以獲取 db_device.id

        if db_device.id is None:
             raise ValueError("Failed to get ID for the new device.")

        # 2. 創建 Transmitter 記錄
        db_transmitter = Transmitter(
            id=db_device.id, # 使用 Device 的 ID
            transmitter_type=TransmitterType.INTERFERER # 固定為 INTERFERER
            # 如果 Interferer 有額外屬性，在這裡設置
        )
        db.add(db_transmitter)
        await db.commit()
        await db.refresh(db_device) # 刷新以包含可能由 DB 產生的預設值或觸發器結果
        # 不需要 refresh db_transmitter，因為我們主要返回 Device
        logger.info(f"Successfully created interferer '{db_device.name}' with ID {db_device.id}")
        return db_device
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating interferer '{obj_in.name}': {e}", exc_info=True)
        raise # 重新拋出異常，讓上層處理

# --- Get Interferer by ID ---
async def get_interferer(db: AsyncSession, interferer_id: int) -> Optional[Device]:
    """
    根據 ID 獲取單個干擾源設備 (確保其類型正確)。
    查詢會包含位置的 WKT 表示。
    """
    logger.debug(f"Fetching interferer with ID: {interferer_id}")
    stmt = (
        select(Device, ST_AsText(Device.position).label('position_wkt'))
        .join(Transmitter, Device.id == Transmitter.id)
        .where(Device.id == interferer_id)
        .where(Device.device_type == DeviceType.TRANSMITTER)
        .where(Transmitter.transmitter_type == TransmitterType.INTERFERER)
    )
    result = await db.execute(stmt)
    # result.first() 返回一個包含 Device 和 WKT 字串的 Row 物件
    # 我們只需要 Device 物件，SQLModel 的 orm_mode 會處理關聯
    db_obj_row = result.first()
    if db_obj_row:
         # db_obj_row[0] 是 Device 物件
         # db_obj_row[1] 是 WKT 字串，可以用於 Schema
         # SQLModel 的 orm_mode 可能會自動處理，但為了明確，可以這樣訪問
         device_obj = db_obj_row[0]
         # 你可以選擇將 WKT 附加到物件上，如果 Schema 需要
         # device_obj.position_wkt = db_obj_row[1]
         return device_obj
    return None

# --- Get Multiple Interferers ---
async def get_multi_interferers(
    db: AsyncSession, *, skip: int = 0, limit: int = 100
) -> Sequence[Device]:
    """
    獲取干擾源設備列表 (確保其類型正確)。
    查詢會包含位置的 WKT 表示。
    """
    logger.debug(f"Fetching multiple interferers (skip={skip}, limit={limit})")
    stmt = (
        select(Device, ST_AsText(Device.position).label('position_wkt'))
        .join(Transmitter, Device.id == Transmitter.id)
        .where(Device.device_type == DeviceType.TRANSMITTER)
        .where(Transmitter.transmitter_type == TransmitterType.INTERFERER)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    # result.all() 返回 Row 物件列表
    # 我們只需要 Device 物件部分
    devices = [row[0] for row in result.all()]
    return devices

# --- Update Interferer ---
async def update_interferer(
    db: AsyncSession, *, db_obj: Device, obj_in: InterfererUpdate
) -> Device:
    """
    更新一個干擾源設備。
    注意：Transmitter 表目前沒有可更新的特定於干擾源的欄位。
         如果未來添加了，需要同時更新 Transmitter 記錄。
    """
    logger.info(f"Attempting to update interferer ID: {db_obj.id}")
    update_data = obj_in.dict(exclude_unset=True) # 只獲取被設定的欄位

    # 處理 Position 更新
    if "position" in update_data and update_data["position"] is not None:
        position_wkt = create_point_wkt(*update_data["position"])
        update_data["position"] = position_wkt # 用 WKT 替換列表

    # 更新 Device 物件
    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(f"Successfully updated interferer ID: {db_obj.id}")
    return db_obj

# --- Delete Interferer ---
async def remove_interferer(db: AsyncSession, *, interferer_id: int) -> Optional[Device]:
    """
    根據 ID 刪除一個干擾源設備。
    由於 Transmitter 表的外鍵設定了 ON DELETE CASCADE，相關的 Transmitter 記錄會自動刪除。
    """
    logger.info(f"Attempting to delete interferer ID: {interferer_id}")
    # 先獲取物件以便返回，同時確認存在且類型正確
    db_obj = await get_interferer(db, interferer_id)
    if db_obj:
        await db.delete(db_obj)
        await db.commit()
        logger.info(f"Successfully deleted interferer ID: {interferer_id}")
        return db_obj
    else:
        logger.warning(f"Interferer with ID {interferer_id} not found for deletion.")
        return None