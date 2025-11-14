"""
Schema 基类
提供通用的序列化功能
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, model_serializer


def serialize_datetime_fields(data: Any) -> Any:
    """
    递归地将所有 datetime 字段转换为 ISO 格式字符串

    Args:
        data: 要序列化的数据（可以是 dict, list, datetime 或其他类型）

    Returns:
        序列化后的数据
    """
    if isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, dict):
        return {key: serialize_datetime_fields(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [serialize_datetime_fields(item) for item in data]
    elif isinstance(data, BaseModel):
        # 如果是 Pydantic 模型, 递归处理其字段
        return serialize_datetime_fields(data.model_dump())
    else:
        return data


class BaseResponseModel(BaseModel):
    """
    响应模型基类

    自动将所有 datetime 字段序列化为 ISO 格式字符串
    所有响应模型应继承此类
    """

    class Config:
        from_attributes = True

    @model_serializer(mode="wrap")
    def serialize_model(self, serializer, _info):
        """
        全局序列化器: 自动将 datetime 字段转换为 ISO 格式字符串
        """
        data = serializer(self)
        return serialize_datetime_fields(data)
