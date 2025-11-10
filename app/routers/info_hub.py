from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.db import get_db
from app.schemas.info_hub import InfoHubCreate, InfoHubUpdate, InfoHubResponse
from app.services.crawler import crawler_service

router = APIRouter(prefix="/info-hub", tags=["信息中心"])


@router.get("/", response_model=List[InfoHubResponse])
async def get_info_hub_list(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    """
    获取信息中心列表
    """
    # TODO: 实现数据库查询逻辑
    return []


@router.post("/", response_model=InfoHubResponse)
async def create_info_hub(info: InfoHubCreate, db: AsyncSession = Depends(get_db)):
    """
    创建信息中心条目
    """
    # TODO: 实现数据库创建逻辑
    raise HTTPException(status_code=501, detail="功能待实现")


@router.get("/{info_id}", response_model=InfoHubResponse)
async def get_info_hub(info_id: int, db: AsyncSession = Depends(get_db)):
    """
    获取单个信息中心条目
    """
    # TODO: 实现数据库查询逻辑
    raise HTTPException(status_code=404, detail="信息中心条目不存在")


@router.put("/{info_id}", response_model=InfoHubResponse)
async def update_info_hub(
    info_id: int, info: InfoHubUpdate, db: AsyncSession = Depends(get_db)
):
    """
    更新信息中心条目
    """
    # TODO: 实现数据库更新逻辑
    raise HTTPException(status_code=404, detail="信息中心条目不存在")


@router.delete("/{info_id}")
async def delete_info_hub(info_id: int, db: AsyncSession = Depends(get_db)):
    """
    删除信息中心条目
    """
    # TODO: 实现数据库删除逻辑
    raise HTTPException(status_code=404, detail="信息中心条目不存在")


@router.post("/crawl")
async def crawl_url(url: str):
    """
    爬取指定 URL 的内容
    """
    result = await crawler_service.fetch_url(url)
    if result is None:
        raise HTTPException(status_code=400, detail="抓取失败")
    return result
