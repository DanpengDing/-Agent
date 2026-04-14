"""

创建FastAPI实例 并且管理所有的路由

"""
import logging
logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)
import  uvicorn
from fastapi import FastAPI
from api.routers import router
def  create_fast_api()->FastAPI:


    # 1. 创建FastApi实例
    app=FastAPI(title="Knowledge API")


    # 2. 注册各种路由
    app.include_router(router=router)

    # 3.返回创建的FastAPI
    return app



if __name__ == '__main__':
    print("1.准备启动Web服务器")
    try:
        uvicorn.run(app=create_fast_api(),host="127.0.0.1",port=8001)
        logger.info("2.启动Web服务器成功...")
    except KeyboardInterrupt as e:
        logger.error(f"2.启动Web服务器失败: {str(e)}")














