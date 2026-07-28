"""初始化数据库脚本"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import engine, Base
from app.models import *  # noqa 导入所有模型以确保注册


async def init_db():
    """创建所有数据库表"""
    print("正在初始化数据库...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("数据库表创建完成！")


if __name__ == "__main__":
    asyncio.run(init_db())
