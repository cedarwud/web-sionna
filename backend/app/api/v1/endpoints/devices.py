# backend/app/api/v1/endpoints/devices.py
import logging
from typing import List, Any, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import get_session
from app.db.models import Device, DeviceType, TransmitterType, Transmitter
from app.schemas.device import Device as DeviceSchema, DeviceCreate, DeviceUpdate
from app.schemas.interferer import InterfererCreate, InterfererUpdate, Interferer
from app.crud import crud_device

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=DeviceSchema)
async def create_new_device(
    *,
    session: AsyncSession = Depends(get_session),
    device_in: DeviceCreate,
) -> Any:
    """
    創建一個新的設備。
    """
    logger.info(f"API: Received request to create device: {device_in.name}")
    # 檢查名稱是否已存在
    existing_device = await crud_device.get_device_by_name(
        db=session, name=device_in.name
    )
    if existing_device:
        logger.warning(f"Device name '{device_in.name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A device with this name already exists.",
        )
    try:
        created_device = await crud_device.create_device(db=session, obj_in=device_in)
        return DeviceSchema.from_orm(created_device)
    except Exception as e:
        logger.error(f"API Error creating device: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the device: {str(e)}",
        )


@router.post(
    "/interferer", status_code=status.HTTP_201_CREATED, response_model=DeviceSchema
)
async def create_new_interferer(
    *,
    session: AsyncSession = Depends(get_session),
    interferer_in: InterfererCreate,
) -> Any:
    """
    創建一個新的干擾源設備 (Transmitter with type INTERFERER)。
    """
    logger.info(f"API: Received request to create interferer: {interferer_in.name}")
    # 檢查名稱是否已存在
    existing_device = await crud_device.get_device_by_name(
        db=session, name=interferer_in.name
    )
    if existing_device:
        logger.warning(f"Device name '{interferer_in.name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A device with this name already exists.",
        )
    try:
        created_device = await crud_device.create_interferer(
            db=session, obj_in=interferer_in
        )
        # 確保返回一個有效的 Device 對象
        interferer_db = await crud_device.get_device(
            db=session, device_id=created_device.id
        )
        if not interferer_db:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve interferer after creation."
            )
        return DeviceSchema.from_orm(interferer_db)
    except Exception as e:
        logger.error(f"API Error creating interferer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the interferer: {str(e)}",
        )


@router.get("/", response_model=List[DeviceSchema])
async def read_devices(
    session: AsyncSession = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
    device_type: Optional[DeviceType] = Query(
        None, description="Filter by device type"
    ),
    transmitter_type: Optional[TransmitterType] = Query(
        None, description="Filter by transmitter type (only for TRANSMITTER devices)"
    ),
) -> Any:
    """
    獲取設備列表，可選按設備類型和發射器類型過濾。
    """
    logger.info(
        f"API: Received request to read devices (skip={skip}, limit={limit}, type={device_type}, tx_type={transmitter_type})"
    )

    if transmitter_type and (
        device_type is None or device_type != DeviceType.TRANSMITTER
    ):
        # 如果指定了發射器類型但設備類型不是發射器，則設置設備類型為發射器
        device_type = DeviceType.TRANSMITTER
        logger.info(
            f"Setting device_type to TRANSMITTER as transmitter_type was specified"
        )

    # 根據參數決定使用哪個查詢函數
    if device_type == DeviceType.TRANSMITTER and transmitter_type:
        # 特定類型的發射器
        devices = await crud_device.get_transmitters_by_type(
            db=session, transmitter_type=transmitter_type, skip=skip, limit=limit
        )
    elif transmitter_type == TransmitterType.INTERFERER:
        # 干擾源 - 使用專門的干擾源查詢
        devices = await crud_device.get_multi_interferers(
            db=session, skip=skip, limit=limit
        )
    else:
        # 一般設備查詢
        devices = await crud_device.get_multi_devices(
            db=session, skip=skip, limit=limit, device_type=device_type
        )

    return [DeviceSchema.from_orm(device) for device in devices]


@router.get("/interferers", response_model=List[DeviceSchema])
async def read_interferers(
    session: AsyncSession = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    獲取干擾源列表。
    """
    logger.info(
        f"API: Received request to read interferers (skip={skip}, limit={limit})"
    )
    interferers = await crud_device.get_multi_interferers(
        db=session, skip=skip, limit=limit
    )
    return [DeviceSchema.from_orm(inf) for inf in interferers]


@router.get("/{device_id}", response_model=DeviceSchema)
async def read_device_by_id(
    device_id: int,
    session: AsyncSession = Depends(get_session),
    as_interferer: bool = Query(
        False, description="Try to get the device as an interferer"
    ),
) -> Any:
    """
    根據 ID 獲取單個設備。
    如果 as_interferer 為 True 時，會嘗試將設備作為干擾源返回，
    但如果不是干擾源，則將返回一般設備數據。
    """
    logger.info(
        f"API: Received request to read device with ID: {device_id}, as_interferer={as_interferer}"
    )

    if as_interferer:
        # 嘗試作為干擾源獲取
        device = await crud_device.get_interferer(db=session, interferer_id=device_id)
        if device:
            # 如果是干擾源，則使用單獨的端點返回
            return await read_interferer_by_id(device_id, session)

    # 常規獲取設備
    device = await crud_device.get_device(db=session, device_id=device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )

    return DeviceSchema.from_orm(device)


@router.get("/interferer/{interferer_id}", response_model=DeviceSchema)
async def read_interferer_by_id(
    interferer_id: int,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    根據 ID 獲取單個干擾源。
    """
    logger.info(f"API: Received request to read interferer with ID: {interferer_id}")
    interferer = await crud_device.get_interferer(
        db=session, interferer_id=interferer_id
    )
    if not interferer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interferer not found"
        )
    return DeviceSchema.from_orm(interferer)


@router.put("/{device_id}", response_model=DeviceSchema)
async def update_existing_device(
    *,
    session: AsyncSession = Depends(get_session),
    device_id: int,
    device_in: DeviceUpdate,
) -> Any:
    """
    更新一個已存在的設備。
    """
    logger.info(f"API: Received request to update device ID: {device_id}")
    db_device = await crud_device.get_device(db=session, device_id=device_id)
    if not db_device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )

    # 檢查更新的名稱是否與其他 Device 衝突
    if device_in.name and device_in.name != db_device.name:
        existing_device = await crud_device.get_device_by_name(
            db=session, name=device_in.name
        )
        if existing_device and existing_device.id != device_id:
            logger.warning(
                f"Updated name '{device_in.name}' conflicts with another device."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Another device with this updated name already exists.",
            )
    try:
        updated_device = await crud_device.update_device(
            db=session, db_obj=db_device, obj_in=device_in
        )
        return DeviceSchema.from_orm(updated_device)
    except Exception as e:
        logger.error(f"API Error updating device ID {device_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating the device: {str(e)}",
        )


@router.put("/interferer/{interferer_id}", response_model=DeviceSchema)
async def update_existing_interferer(
    *,
    session: AsyncSession = Depends(get_session),
    interferer_id: int,
    interferer_in: InterfererUpdate,
) -> Any:
    """
    更新一個已存在的干擾源。
    """
    logger.info(f"API: Received request to update interferer ID: {interferer_id}")
    db_interferer = await crud_device.get_interferer(
        db=session, interferer_id=interferer_id
    )
    if not db_interferer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interferer not found"
        )

    # 檢查更新的名稱是否與其他 Device 衝突
    if interferer_in.name and interferer_in.name != db_interferer.name:
        existing_device = await crud_device.get_device_by_name(
            db=session, name=interferer_in.name
        )
        if existing_device and existing_device.id != interferer_id:
            logger.warning(
                f"Updated name '{interferer_in.name}' conflicts with another device."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Another device with this updated name already exists.",
            )
    try:
        updated_interferer = await crud_device.update_interferer(
            db=session, db_obj=db_interferer, obj_in=interferer_in
        )
        return DeviceSchema.from_orm(updated_interferer)
    except Exception as e:
        logger.error(
            f"API Error updating interferer ID {interferer_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating the interferer: {str(e)}",
        )


@router.delete("/{device_id}", response_model=DeviceSchema)
async def delete_device_by_id(
    *,
    session: AsyncSession = Depends(get_session),
    device_id: int,
) -> Any:
    """
    刪除一個設備。
    """
    logger.info(f"API: Received request to delete device ID: {device_id}")
    deleted_device = await crud_device.remove_device(db=session, device_id=device_id)
    if not deleted_device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    return DeviceSchema.from_orm(deleted_device)


@router.delete("/interferer/{interferer_id}", response_model=DeviceSchema)
async def delete_interferer_by_id(
    *,
    session: AsyncSession = Depends(get_session),
    interferer_id: int,
) -> Any:
    """
    刪除一個干擾源。
    """
    logger.info(f"API: Received request to delete interferer ID: {interferer_id}")
    deleted_interferer = await crud_device.remove_interferer(
        db=session, interferer_id=interferer_id
    )
    if not deleted_interferer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interferer not found"
        )
    return DeviceSchema.from_orm(deleted_interferer)
