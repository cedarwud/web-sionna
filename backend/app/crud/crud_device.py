# backend/app/crud/crud_device.py
import logging
from typing import List, Optional, Sequence, Any, Dict, Union, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from geoalchemy2.functions import ST_GeomFromText, ST_AsText

from app.db.models import Device, Transmitter, Receiver, DeviceType, TransmitterType
from app.schemas.device import DeviceCreate, DeviceUpdate
from app.schemas.interferer import InterfererCreate, InterfererUpdate

logger = logging.getLogger(__name__)


# --- Helper to create WKT string ---
def create_point_wkt(lon: float, lat: float, alt: float) -> str:
    # 使用 SRID 4326 (WGS 84)
    return f"SRID=4326;POINT Z ({lon} {lat} {alt})"


# --- Create Device ---
async def create_device(db: AsyncSession, *, obj_in: DeviceCreate) -> Device:
    """
    創建一個新的設備記錄。
    根據設備類型，可能還會創建對應的 Transmitter 或 Receiver 記錄。
    """
    logger.info(
        f"Attempting to create device: {obj_in.name} of type {obj_in.device_type}"
    )
    try:
        # 1. 創建 Device 記錄
        db_device = Device(
            name=obj_in.name,
            device_type=obj_in.device_type,
            x=obj_in.x,
            y=obj_in.y,
            z=obj_in.z,
            active=obj_in.active,
        )
        db.add(db_device)
        await db.flush()  # 刷新以獲取 db_device.id

        if db_device.id is None:
            raise ValueError("Failed to get ID for the new device.")

        # 2. 根據設備類型創建對應的記錄
        if obj_in.device_type == DeviceType.TRANSMITTER:
            # 默認創建 SIGNAL 類型的發射器
            db_transmitter = Transmitter(
                id=db_device.id, transmitter_type=TransmitterType.SIGNAL
            )
            db.add(db_transmitter)
        elif obj_in.device_type == DeviceType.RECEIVER:
            # 創建接收器
            db_receiver = Receiver(id=db_device.id)
            db.add(db_receiver)

        await db.commit()
        await db.refresh(db_device)
        logger.info(
            f"Successfully created device '{db_device.name}' with ID {db_device.id}"
        )
        return db_device
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating device '{obj_in.name}': {e}", exc_info=True)
        raise  # 重新拋出異常，讓上層處理


# --- Create Interferer (整合自 crud_interferer) ---
async def create_interferer(db: AsyncSession, *, obj_in: InterfererCreate) -> Device:
    """
    創建一個新的干擾源設備和對應的發射器記錄。
    """
    logger.info(f"Attempting to create interferer: {obj_in.name}")
    try:
        # 1. 創建 Device 記錄
        db_device = Device(
            name=obj_in.name,
            device_type=DeviceType.TRANSMITTER,  # 固定為 TRANSMITTER
            x=obj_in.x,
            y=obj_in.y,
            z=obj_in.z,
            active=obj_in.active,
        )
        db.add(db_device)
        await db.flush()  # 刷新以獲取 db_device.id

        if db_device.id is None:
            raise ValueError("Failed to get ID for the new device.")

        # 2. 創建 Transmitter 記錄
        db_transmitter = Transmitter(
            id=db_device.id,  # 使用 Device 的 ID
            transmitter_type=TransmitterType.INTERFERER,  # 固定為 INTERFERER
        )
        db.add(db_transmitter)
        await db.commit()
        await db.refresh(db_device)  # 刷新以包含可能由 DB 產生的預設值或觸發器結果
        logger.info(
            f"Successfully created interferer '{db_device.name}' with ID {db_device.id}"
        )
        return db_device
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating interferer '{obj_in.name}': {e}", exc_info=True)
        raise  # 重新拋出異常，讓上層處理


# --- Get Device by ID ---
async def get_device(db: AsyncSession, device_id: int) -> Optional[Device]:
    """
    根據 ID 獲取單個設備。
    """
    logger.debug(f"Fetching device with ID: {device_id}")
    stmt = select(Device).where(Device.id == device_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# --- Get Device by Name ---
async def get_device_by_name(db: AsyncSession, name: str) -> Optional[Device]:
    """
    根據名稱獲取單個設備。
    """
    logger.debug(f"Fetching device with name: {name}")
    stmt = select(Device).where(Device.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# --- Get Interferer by ID (整合自 crud_interferer) ---
async def get_interferer(db: AsyncSession, interferer_id: int) -> Optional[Device]:
    """
    根據 ID 獲取單個干擾源設備 (確保其類型正確)。
    """
    logger.debug(f"Fetching interferer with ID: {interferer_id}")
    stmt = (
        select(Device)
        .join(Transmitter, Device.id == Transmitter.id)
        .where(Device.id == interferer_id)
        .where(Device.device_type == DeviceType.TRANSMITTER)
        .where(Transmitter.transmitter_type == TransmitterType.INTERFERER)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# --- Get Multiple Devices ---
async def get_multi_devices(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    device_type: Optional[DeviceType] = None,
) -> Sequence[Device]:
    """
    獲取設備列表，可選按類型過濾。
    關聯的 Transmitter (如果存在) 會被自動加載 (lazy='joined')。
    """
    logger.debug(
        f"Fetching multiple devices (skip={skip}, limit={limit}, type={device_type})"
    )

    # 基礎查詢，依賴模型定義中的 lazy='joined' 來加載 Transmitter
    query = select(Device)

    # 如果指定了設備類型，添加類型過濾條件
    if device_type:
        query = query.where(Device.device_type == device_type)

    # 添加分頁
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)

    # scalars().all() 應該會返回包含已加載關係的 Device 對象
    return result.scalars().unique().all()  # .unique() 防止 join 可能導致的重複


# --- Get Multiple Interferers (整合自 crud_interferer) ---
async def get_multi_interferers(
    db: AsyncSession, *, skip: int = 0, limit: int = 100
) -> Sequence[Device]:
    """
    獲取干擾源設備列表 (確保其類型正確)。
    關聯的 Transmitter 會被自動加載 (lazy='joined')。
    """
    logger.debug(f"Fetching multiple interferers (skip={skip}, limit={limit})")
    # 因為 Device 模型已經定義了 lazy='joined'，可以直接查詢 Device
    # SQLAlchemy 會自動處理 join 和過濾
    query = (
        select(Device)
        # .options(joinedload(Device.transmitter)) # 如果 lazy='joined' 不可靠，可以明確指定
        .join(Device.transmitter)  # 使用關係進行 join
        .where(Device.device_type == DeviceType.TRANSMITTER)
        .where(Transmitter.transmitter_type == TransmitterType.INTERFERER)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().unique().all()


# --- Update Device ---
async def update_device(
    db: AsyncSession, *, db_obj: Device, obj_in: Union[DeviceUpdate, Dict[str, Any]]
) -> Device:
    """
    更新設備信息。
    """
    logger.info(f"Attempting to update device ID: {db_obj.id}")

    # 將 Pydantic 模型轉換為字典
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)

    # 更新 Device 物件
    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(f"Successfully updated device ID: {db_obj.id}")
    return db_obj


# --- Update Interferer (整合自 crud_interferer) ---
async def update_interferer(
    db: AsyncSession, *, db_obj: Device, obj_in: InterfererUpdate
) -> Device:
    """
    更新一個干擾源設備。
    注意：Transmitter 表目前沒有可更新的特定於干擾源的欄位。
         如果未來添加了，需要同時更新 Transmitter 記錄。
    """
    logger.info(f"Attempting to update interferer ID: {db_obj.id}")
    # 直接使用通用的 update_device 函數
    return await update_device(db=db, db_obj=db_obj, obj_in=obj_in)


# --- Delete Device ---
async def remove_device(db: AsyncSession, *, device_id: int) -> Optional[Device]:
    """
    根據 ID 刪除一個設備。
    由於外鍵關係設置為 ON DELETE CASCADE，相關的 Transmitter 或 Receiver 記錄會自動刪除。
    """
    logger.info(f"Attempting to delete device ID: {device_id}")
    # 先獲取物件以便返回
    db_obj = await get_device(db, device_id)
    if db_obj:
        # 檢查並處理可能的 transmitter 和 receiver 關係
        if hasattr(db_obj, "transmitter") and db_obj.transmitter is not None:
            await db.delete(db_obj.transmitter)
        if hasattr(db_obj, "receiver") and db_obj.receiver is not None:
            await db.delete(db_obj.receiver)

        # 最後刪除 device 本身
        await db.delete(db_obj)
        await db.commit()
        logger.info(f"Successfully deleted device ID: {device_id}")
        return db_obj
    else:
        logger.warning(f"Device with ID {device_id} not found for deletion.")
        return None


# --- Delete Interferer (整合自 crud_interferer) ---
async def remove_interferer(
    db: AsyncSession, *, interferer_id: int
) -> Optional[Device]:
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


# --- 額外輔助函數 ---


async def get_transmitters_by_type(
    db: AsyncSession,
    *,
    transmitter_type: TransmitterType,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
) -> Sequence[Device]:
    """
    獲取特定類型的發射器設備列表。
    關聯的 Transmitter 會被自動加載。
    """
    logger.debug(
        f"Fetching transmitters of type {transmitter_type} (skip={skip}, limit={limit}, active_only={active_only})"
    )
    query = (
        select(Device)
        # .options(joinedload(Device.transmitter))
        .join(Device.transmitter)
        .where(Device.device_type == DeviceType.TRANSMITTER)
        .where(Transmitter.transmitter_type == transmitter_type)
    )

    if active_only:
        query = query.where(Device.active == True)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().unique().all()


async def get_active_devices_by_type(
    db: AsyncSession,
    *,
    device_type: DeviceType = None,
    transmitter_type: TransmitterType = None,
) -> Tuple[List[Device], List[Device]]:
    """
    獲取活動的發射器和接收器設備，可選按發射器類型過濾。
    返回 (transmitters, receivers) 元組。
    Transmitter 會自動加載。
    """
    logger.debug(
        f"Fetching active devices by type (device_type={device_type}, transmitter_type={transmitter_type})"
    )

    transmitters = []
    receivers = []

    # --- 獲取發射器 ---
    if device_type == DeviceType.TRANSMITTER or device_type is None:
        # 查詢 Device，依賴 lazy='joined' 或 joinedload
        tx_query = (
            select(Device)
            # .options(joinedload(Device.transmitter))
            .join(
                Device.transmitter
            )  # join 是必要的，即使 lazy='joined'，以便在 where 中過濾
            .where(Device.active == True)
            .where(Device.device_type == DeviceType.TRANSMITTER)
        )
        # 如果指定了發射器類型，添加過濾條件
        if transmitter_type is not None:
            tx_query = tx_query.where(Transmitter.transmitter_type == transmitter_type)

        tx_result = await db.execute(tx_query)
        transmitters = list(tx_result.scalars().unique().all())

    # --- 獲取接收器 ---
    if device_type == DeviceType.RECEIVER or device_type is None:
        # 接收器不需要連接 Transmitter
        rx_query = (
            select(Device)
            # .options(joinedload(Device.receiver)) # 如果需要加載 receiver 關係
            .where(Device.active == True).where(
                Device.device_type == DeviceType.RECEIVER
            )
        )
        rx_result = await db.execute(rx_query)
        receivers = list(rx_result.scalars().unique().all())

    return transmitters, receivers
