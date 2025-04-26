# backend/app/api/v1/endpoints/interferers.py
import logging
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select # 引入 select

from app.api.deps import get_session # 引用 DB Session 依賴
from app.db.models import Device, Transmitter, DeviceType, TransmitterType # 引用 DB 模型
from app.schemas.interferer import Interferer, InterfererCreate, InterfererUpdate # 引用 Schemas
from app.crud import crud_interferer # 引用 CRUD 操作函數

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Interferer)
async def create_new_interferer(
    *,
    session: AsyncSession = Depends(get_session),
    interferer_in: InterfererCreate,
) -> Any:
    """
    創建一個新的干擾源 (Transmitter with type INTERFERER)。
    """
    logger.info(f"API: Received request to create interferer: {interferer_in.name}")
    # 檢查名稱是否已存在 (作為 Device)
    stmt = select(Device).where(Device.name == interferer_in.name)
    result = await session.execute(stmt)
    existing_device = result.scalar_one_or_none()
    if existing_device:
        logger.warning(f"Device name '{interferer_in.name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A device with this name already exists.",
        )
    try:
        created_device = await crud_interferer.create_interferer(db=session, obj_in=interferer_in)
        # 為了符合 Interferer response_model，我們需要從 DB 重新獲取包含 WKT 的資訊
        # 或者在 CRUD 返回時處理 (目前 CRUD 返回 Device，需要調整以符合 Interferer Schema)
        # 暫時直接從創建結果轉換，但 position 會是內部格式，需要調整 Schema 或 CRUD
        # 為確保返回數據一致，最好是重新查詢一次
        interferer_db = await crud_interferer.get_interferer(db=session, interferer_id=created_device.id)
        if not interferer_db:
             # 這不應該發生，但作為防禦性程式設計
             raise HTTPException(status_code=500, detail="Failed to retrieve interferer after creation.")
        # 手動轉換以匹配 Schema (如果 Schema 需要列表格式的位置)
        pos_list = None
        if interferer_db.position: # position 存的是 WKT 或內部 Geometry
             # 需要從 WKT 或 Geometry 轉換回列表
             # 假設 get_interferer 返回時已轉換或 Schema 能處理
             pass # 暫時忽略轉換細節，依賴 Schema 的 orm_mode 和 alias
        return Interferer.from_orm(interferer_db) # 使用 Interferer Schema
    except Exception as e:
        logger.error(f"API Error creating interferer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the interferer: {str(e)}",
        )

@router.get("/", response_model=List[Interferer])
async def read_interferers(
    session: AsyncSession = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    獲取干擾源列表。
    """
    logger.info(f"API: Received request to read interferers (skip={skip}, limit={limit})")
    interferers = await crud_interferer.get_multi_interferers(db=session, skip=skip, limit=limit)
    # 同上，需要確保返回的物件符合 Interferer Schema
    return [Interferer.from_orm(inf) for inf in interferers]

@router.get("/{interferer_id}", response_model=Interferer)
async def read_interferer_by_id(
    interferer_id: int,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    根據 ID 獲取單個干擾源。
    """
    logger.info(f"API: Received request to read interferer with ID: {interferer_id}")
    interferer = await crud_interferer.get_interferer(db=session, interferer_id=interferer_id)
    if not interferer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interferer not found")
    return Interferer.from_orm(interferer)

@router.put("/{interferer_id}", response_model=Interferer)
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
    db_interferer = await crud_interferer.get_interferer(db=session, interferer_id=interferer_id)
    if not db_interferer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interferer not found")

    # 檢查更新的名稱是否與其他 Device 衝突 (如果名稱被更新)
    if interferer_in.name and interferer_in.name != db_interferer.name:
        stmt = select(Device).where(Device.name == interferer_in.name).where(Device.id != interferer_id)
        result = await session.execute(stmt)
        existing_device = result.scalar_one_or_none()
        if existing_device:
             logger.warning(f"Updated name '{interferer_in.name}' conflicts with another device.")
             raise HTTPException(
                 status_code=status.HTTP_400_BAD_REQUEST,
                 detail="Another device with this updated name already exists.",
             )
    try:
        updated_interferer = await crud_interferer.update_interferer(
            db=session, db_obj=db_interferer, obj_in=interferer_in
        )
        return Interferer.from_orm(updated_interferer)
    except Exception as e:
        logger.error(f"API Error updating interferer ID {interferer_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating the interferer: {str(e)}",
         )


@router.delete("/{interferer_id}", response_model=Interferer)
async def delete_interferer_by_id(
    *,
    session: AsyncSession = Depends(get_session),
    interferer_id: int,
) -> Any:
    """
    刪除一個干擾源。
    """
    logger.info(f"API: Received request to delete interferer ID: {interferer_id}")
    deleted_interferer = await crud_interferer.remove_interferer(db=session, interferer_id=interferer_id)
    if not deleted_interferer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interferer not found")
    # 返回被刪除的物件信息
    return Interferer.from_orm(deleted_interferer)