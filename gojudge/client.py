from __future__ import annotations

import httpx
import logging
from gojudge.schemas import *
# from task import JudgeTask
from contextlib import asynccontextmanager
from typing import Any
import asyncio
logger = logging.getLogger(__name__)
class SandboxErrorBase(Exception):
    pass
class SandboxConnError(SandboxErrorBase):
    pass

class SandboxAPIError(SandboxErrorBase):
    pass

class GoJudgeClient:
    """
    封装与gojudge的http2 通信 通过request方法
    task_scope 配合async with 实现自动清理文件缓存
    """
    def __init__(
        self, 
        compute_semaphore : asyncio.Semaphore,
        base_url: str = "http://localhost:5050", 
        timeout: float = 60.0,
        max_connections: int = 100,
        
    ):
        self._base_url = base_url.rstrip("/")
        limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max(20,max_connections//2),
            keepalive_expiry=60.0
        )
        
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            limits=limits,
            timeout=httpx.Timeout(timeout,connect=10.0),
            http2=True
        )
        self.compute_semaphore = compute_semaphore

    async def __aenter__(self):
        return self
    
    async def __aexit__(self,exc_type,exc_val,exc_tb):
        await self.close()

    
    async def close(self):
        await self._client.aclose()

    @asynccontextmanager
    async def task_context(self):
        ctx = TaskContext(self)
        try:
            yield ctx
        finally:
            await ctx.cleanup()

    
    async def request(self,method:str,path:str,**kwargs)->Any:
        try:
            response = await self._client.request(method,path,**kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise SandboxAPIError(f"http状态码有误: {str(e)}")
        except httpx.RequestError as e:
            raise SandboxConnError(f"连接沙箱失败:{str(e)}")
        


class TaskContext:
    #需要增加编译后可执行文件的清理
    def __init__(self,client:GoJudgeClient) -> None:
        self.client = client
        self.cached_file_ids : list[str] = []
    
    async def upload_file(self,name:str,content:str)->str:
        files = {"file":(name,content)}
        data = await self.client.request("POST","/file",files=files)
        file_ID = data["fileId"]
        self.cached_file_ids.append(file_ID)
        return file_ID
    async def delete_file(self,file_id:str)->bool:
        try:
            res = await self.client._client.delete(f"/file/{file_id}")
            if res.status_code not in(200,404):
                logger.warning(f"文件:{file_id}清理失败,http_code:{res.status_code},响应:{res}")
                return False
        except Exception as e:
            logger.warning(f"文件:{file_id}清理失败,异常信息:{e}")
            return False
        return True
    async def run_task(self,request:Request)->list[Result]:
        payload = request.model_dump(by_alias=True,exclude_none=True)#预先序列化,考虑是否excludedefault
        logger.debug(f"{payload}")
        async with self.client.compute_semaphore:#通过全局唯一的计算信号量，控制发给gojudge同时跑的测试点的数量
            data = await self.client.request("POST","/run",json=payload)
            return [Result.model_validate(item) for item in data]
        
    async def register_file(self,file_id:str):
        if file_id not in self.cached_file_ids:
            self.cached_file_ids.append(file_id)
            
    async def unregister_file(self,file_id:str):
        self.cached_file_ids = [x for x in self.cached_file_ids if x!=file_id]

    async def cleanup(self):
        if not self.cached_file_ids:
            return
        
        tasks = [
            self.client._client.delete(f"/file/{file_id}")
            for file_id in self.cached_file_ids
        ]
        results = await asyncio.gather(*tasks,return_exceptions=True)
        for i,res in enumerate(results):
            if isinstance(res,Exception):
                logger.warning(f"Failed to cleanup file {self.cached_file_ids[i]}: {res}")
            elif isinstance(res,httpx.Response):
                if res.status_code not in(200,404):
                    logger.warning(f"Failed to cleanup file {self.cached_file_ids[i]}: Status {res.status_code}")

        self.cached_file_ids.clear()