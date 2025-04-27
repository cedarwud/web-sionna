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
            # 檢查是否提供了transmitter_type，如果有就使用它，否則默認為SIGNAL
            tx_type = (
                obj_in.transmitter_type
                if hasattr(obj_in, "transmitter_type") and obj_in.transmitter_type
                else TransmitterType.SIGNAL
            )

            db_transmitter = Transmitter(id=db_device.id, transmitter_type=tx_type)
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


# --- Update Device By ID (避免使用已刪除的對象) ---
async def update_device_by_id(
    db: AsyncSession, *, device_id: int, device_in: Union[DeviceUpdate, Dict[str, Any]]
) -> Device:
    """
    根據ID更新設備信息，避免傳遞可能已刪除的對象。
    """
    logger.info(f"Attempting to update device by ID: {device_id}")

    # 將 Pydantic 模型轉換為字典
    if isinstance(device_in, dict):
        update_data = device_in.copy()
    else:
        update_data = device_in.dict(exclude_unset=True)

    # 提取transmitter_type以便稍後使用
    transmitter_type = (
        update_data.pop("transmitter_type", None)
        if "transmitter_type" in update_data
        else None
    )

    # 獲取當前設備數據
    db_device = await get_device(db=db, device_id=device_id)
    if not db_device:
        logger.warning(f"Device with ID {device_id} not found for update.")
        raise ValueError(f"Device with ID {device_id} not found")

    # 獲取並保存完整的設備信息（用於可能需要重建）
    device_info = {
        "id": db_device.id,
        "name": db_device.name,
        "device_type": db_device.device_type,
        "x": db_device.x,
        "y": db_device.y,
        "z": db_device.z,
        "active": db_device.active,
    }

    # 更新device_info中的數據
    for field, value in update_data.items():
        device_info[field] = value

    # 檢查是否變更了設備類型
    device_type_changed = (
        "device_type" in update_data
        and update_data["device_type"] != db_device.device_type
    )

    # 保存新的設備類型和其他更新數據
    new_device_type = update_data.get("device_type", db_device.device_type)

    try:
        # 如果設備類型變更，先處理關聯記錄，不使用額外的事務包裝
        if device_type_changed:
            # 1. 刪除現有的關聯記錄
            if db_device.device_type == DeviceType.RECEIVER:
                stmt = select(Receiver).where(Receiver.id == device_id)
                result = await db.execute(stmt)
                receiver = result.scalar_one_or_none()
                if receiver:
                    await db.delete(receiver)
                    await db.flush()
            elif db_device.device_type == DeviceType.TRANSMITTER:
                stmt = select(Transmitter).where(Transmitter.id == device_id)
                result = await db.execute(stmt)
                transmitter = result.scalar_one_or_none()
                if transmitter:
                    await db.delete(transmitter)
                    await db.flush()

            # 2. 更新設備基本信息
            stmt = select(Device).where(Device.id == device_id)
            result = await db.execute(stmt)
            device = result.scalar_one_or_none()

            if not device:
                # 設備在刪除關聯記錄後不存在了，需要重新創建
                logger.warning(
                    f"Device with ID {device_id} was deleted during update - recreating"
                )
                new_device = Device(
                    id=device_id,
                    name=device_info["name"],
                    device_type=device_info["device_type"],
                    x=device_info["x"],
                    y=device_info["y"],
                    z=device_info["z"],
                    active=device_info["active"],
                )
                db.add(new_device)
                await db.flush()
                device = new_device
            else:
                # 更新現有設備
                for field, value in update_data.items():
                    setattr(device, field, value)

                db.add(device)
                await db.flush()

            # 3. 創建新的關聯記錄
            if new_device_type == DeviceType.TRANSMITTER:
                # 創建新的發射器記錄
                tx_type = (
                    transmitter_type
                    if transmitter_type is not None
                    else TransmitterType.SIGNAL
                )
                db_transmitter = Transmitter(id=device_id, transmitter_type=tx_type)
                db.add(db_transmitter)
            elif new_device_type == DeviceType.RECEIVER:
                # 創建新的接收器記錄
                db_receiver = Receiver(id=device_id)
                db.add(db_receiver)
        else:
            # 常規更新 - 無設備類型變更
            # 更新設備基本信息
            stmt = select(Device).where(Device.id == device_id)
            result = await db.execute(stmt)
            device = result.scalar_one_or_none()

            if not device:
                # 設備不存在，需要重新創建
                logger.warning(
                    f"Device with ID {device_id} not found during update - recreating"
                )
                new_device = Device(
                    id=device_id,
                    name=device_info["name"],
                    device_type=device_info["device_type"],
                    x=device_info["x"],
                    y=device_info["y"],
                    z=device_info["z"],
                    active=device_info["active"],
                )
                db.add(new_device)
                await db.flush()
                device = new_device
            else:
                # 更新現有設備
                for field, value in update_data.items():
                    setattr(device, field, value)

                db.add(device)
                await db.flush()

            # 處理發射器類型變更（當設備類型沒變，但發射器類型變了）
            if (
                device.device_type == DeviceType.TRANSMITTER
                and transmitter_type is not None
            ):
                # 查詢發射器記錄
                stmt = select(Transmitter).where(Transmitter.id == device_id)
                result = await db.execute(stmt)
                transmitter = result.scalar_one_or_none()

                if transmitter:
                    transmitter.transmitter_type = transmitter_type
                    db.add(transmitter)
                else:
                    # 如果沒有，創建一個
                    db_transmitter = Transmitter(
                        id=device_id, transmitter_type=transmitter_type
                    )
                    db.add(db_transmitter)

        # 提交變更
        await db.commit()

        # 重新獲取更新後的設備，包括所有關聯的記錄
        updated_device = await get_device(db=db, device_id=device_id)

        if not updated_device:
            # 如果在提交後仍無法找到設備，返回根據保存信息重建的設備對象
            logger.error(f"Device with ID {device_id} could not be found after update")
            updated_device = Device(
                id=device_id,
                name=device_info["name"],
                device_type=new_device_type,
                x=device_info["x"],
                y=device_info["y"],
                z=device_info["z"],
                active=device_info["active"],
            )

        logger.info(f"Successfully updated device by ID: {device_id}")
        return updated_device

    except Exception as e:
        logger.error(f"Error updating device ID {device_id}: {e}", exc_info=True)
        # 嘗試回滾以確保數據庫一致性
        try:
            await db.rollback()
        except:
            pass
        raise


# --- Update Interferer (整合自 crud_interferer) ---
async def update_interferer(
    db: AsyncSession, *, db_obj: Device, obj_in: InterfererUpdate
) -> Device:
    """
    更新一個干擾源設備（兼容性版本）。
    """
    logger.info(
        f"Attempting to update interferer ID: {db_obj.id} using compatibility function"
    )
    # 使用新的by_id版本
    return await update_interferer_by_id(db=db, interferer_id=db_obj.id, obj_in=obj_in)


# --- Delete Device ---
async def remove_device(db: AsyncSession, *, device_id: int) -> Optional[Device]:
    """
    根據 ID 刪除一個設備。
    先刪除相關的 Transmitter 或 Receiver 記錄，然後再刪除 Device 記錄。
    """
    logger.info(f"Attempting to delete device ID: {device_id}")

    # 先獲取並複製設備信息以便返回
    db_obj = await get_device(db, device_id)
    if not db_obj:
        logger.warning(f"Device with ID {device_id} not found for deletion.")
        return None

    # 保存返回數據的副本
    device_copy = Device(
        id=db_obj.id,
        name=db_obj.name,
        device_type=db_obj.device_type,
        x=db_obj.x,
        y=db_obj.y,
        z=db_obj.z,
        active=db_obj.active,
    )

    try:
        # 檢查並先刪除 receiver 關係
        if hasattr(db_obj, "receiver") and db_obj.receiver is not None:
            await db.delete(db_obj.receiver)
            await db.flush()

        # 檢查並刪除 transmitter 關係
        if hasattr(db_obj, "transmitter") and db_obj.transmitter is not None:
            await db.delete(db_obj.transmitter)
            await db.flush()

        # 最後刪除 device 本身
        await db.delete(db_obj)
        await db.commit()
        logger.info(f"Successfully deleted device ID: {device_id}")
        return device_copy
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting device ID {device_id}: {e}", exc_info=True)
        raise


# --- Delete Interferer (整合自 crud_interferer) ---
async def remove_interferer(
    db: AsyncSession, *, interferer_id: int
) -> Optional[Device]:
    """
    根據 ID 刪除一個干擾源設備。
    先確保存在且類型正確，然後執行刪除。
    """
    logger.info(f"Attempting to delete interferer ID: {interferer_id}")

    # 先獲取並複製設備信息以便返回，同時確認存在且類型正確
    db_obj = await get_interferer(db, interferer_id)
    if not db_obj:
        logger.warning(f"Interferer with ID {interferer_id} not found for deletion.")
        return None

    # 保存返回數據的副本
    device_copy = Device(
        id=db_obj.id,
        name=db_obj.name,
        device_type=db_obj.device_type,
        x=db_obj.x,
        y=db_obj.y,
        z=db_obj.z,
        active=db_obj.active,
    )

    try:
        # 先刪除發射器記錄
        if hasattr(db_obj, "transmitter") and db_obj.transmitter is not None:
            await db.delete(db_obj.transmitter)
            await db.flush()

        # 然後刪除設備記錄
        await db.delete(db_obj)
        await db.commit()
        logger.info(f"Successfully deleted interferer ID: {interferer_id}")
        return device_copy
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Error deleting interferer ID {interferer_id}: {e}", exc_info=True
        )
        raise


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


# --- Update Interferer By ID ---
async def update_interferer_by_id(
    db: AsyncSession, *, interferer_id: int, obj_in: InterfererUpdate
) -> Device:
    """
    根據ID更新干擾源設備信息，避免傳遞可能已刪除的對象。
    """
    logger.info(f"Attempting to update interferer by ID: {interferer_id}")

    # 轉換為設備更新格式
    device_update_data = obj_in.dict(exclude_unset=True)
    # 確保設備類型為發射器
    device_update_data["device_type"] = DeviceType.TRANSMITTER
    # 設置發射器類型為干擾器
    device_update_data["transmitter_type"] = TransmitterType.INTERFERER

    # 使用通用的update_device_by_id函數
    return await update_device_by_id(
        db=db, device_id=interferer_id, device_in=device_update_data
    )


# --- Update Device ---
async def update_device(
    db: AsyncSession, *, db_obj: Device, obj_in: Union[DeviceUpdate, Dict[str, Any]]
) -> Device:
    """
    更新設備信息（兼容性版本）。
    """
    logger.info(
        f"Attempting to update device ID: {db_obj.id} using compatibility function"
    )
    # 調用新的by_id版本
    return await update_device_by_id(db=db, device_id=db_obj.id, device_in=obj_in)
