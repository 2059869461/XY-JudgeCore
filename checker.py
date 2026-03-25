from __future__ import annotations
from gojudge.client import GoJudgeClient,TaskContext
from languages import Language
from typing import TYPE_CHECKING
from cachetools import LRUCache
from config import settings
import asyncio
if TYPE_CHECKING:
    from processor import TaskProcessor
"""
TODO:
    1 加锁避免多个判题请求并发导致checker重复编译
    2 引入lru 精准淘汰最长时间未使用的checker 并同步清理沙箱的文件
    3 考虑沙箱异常情况，比如重启后导致缓存的checker失效，目前考虑方案是检查沙箱异常之后等待恢复之后调用GET /file 获取所有文件
    淘汰本地缓存了但是file没得到的，同时捕获到fileerror的时候，清理对应题目的checker 作为兜底机制
"""
class CheckerCompileError(Exception):
    def __init__(self, message,problem_id:int|None=None) -> None:
        super().__init__(message)
        self.problem_id = problem_id
class CheckerManager():
    def __init__(self,ctx:TaskContext,client:GoJudgeClient,processor:TaskProcessor) -> None:
        self.client = client
        self._default_checker:str|None = None
        self._spj_checkers :LRUCache[int,str]= LRUCache(maxsize=settings.checker_cache_size)
        self._processor = processor
        self._ctx = ctx
        self._lock = asyncio.Lock()#串行化编译，避免同一个problem 的checker被多次编译
    async def _compile_checker(self,problem_id:int|None=None)->str:
        if problem_id is None:
            language = Language.CHECKER#标准checker采用特定配置编译,静态链接减少开销
            with open("./checker.cpp","r") as f:
                src = f.read()
        else:
            language = Language.CPP17
            with open("./spj.cpp","r") as f:
                src = f.read() #需要引入版本管理
        compile_ok,file_id = await self._processor.compile(language=language,src=src,ctx=self._ctx)
        if not compile_ok:
            raise CheckerCompileError(f"checker编译失败:{file_id}",problem_id=problem_id)
        return file_id

        
    async def get_checker(self,problem_id:int|None=None)->str:
        if problem_id is None:
            if self._default_checker is None:
                async with self._lock:
                    if self._default_checker is None:
                        self._default_checker = await self._compile_checker()
            return self._default_checker
        else:
            if problem_id in self._spj_checkers:#先检查缓存命中，防止被淘汰的恰巧就是需要的
                return self._spj_checkers[problem_id]
            async with self._lock:
                if problem_id in self._spj_checkers:
                    return self._spj_checkers[problem_id]
                if len(self._spj_checkers) >= self._spj_checkers.maxsize:
                    old_key = next(iter(self._spj_checkers))
                    old_file_id = self._spj_checkers.pop(old_key)
                    await self._ctx.delete_file(old_file_id)

                file_id = await self._compile_checker(problem_id)
                self._spj_checkers[problem_id] = file_id
                return file_id
    
    async def remove_invalid_ids(self):
        data = await self.client.request("GET","/file")# 返回 dict {fileId: name}
        sandbox_ids = set(data.keys())
        if self._default_checker and self._default_checker not in sandbox_ids:
            self._default_checker = None

        for k in list(self._spj_checkers.keys()):
            if self._spj_checkers[k] not in sandbox_ids:#集合查找复杂度O(1)
                self._ctx.unregister_file(self._spj_checkers[k])
                del self._spj_checkers[k]

