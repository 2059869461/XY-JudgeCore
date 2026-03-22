from __future__ import annotations
from .gojudge.client import GoJudgeClient,TaskContext
from .languages import Language
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .processor import TaskProcessor

class CheckerCompileError(Exception):
    def __init__(self, message,problem_id:int|None=None) -> None:
        super().__init__(message)
        self.problem_id = problem_id
class CheckerManager():
    def __init__(self,ctx:TaskContext,client:GoJudgeClient,processor:TaskProcessor) -> None:
        self.client = client
        self._default_checker:str|None = None
        self._spj_checkers :dict[int,str] ={}
        self._processor = processor
        self._ctx = ctx
    async def _compile_checker(self,problem_id:int|None=None)->str:
        if problem_id is None:
            language = Language.CHECKER#标准checker采用特定配置编译,静态链接减少开销
            with open("./checker.cpp","r") as f:
                src = f.read()
        else:
            language = Language.CPP17
            src = ""#需要读取spj的代码，暂时先掠过
        compile_ok,file_id = await self._processor.compile(language=language,src=src,ctx=self._ctx)
        if not compile_ok:
            raise CheckerCompileError(f"checker编译失败:{file_id}",problem_id=problem_id)
        await self._ctx.register_file(file_id)
        return file_id

        
    async def get_checker(self,problem_id:int|None=None)->str:
        if problem_id is None:
            if self._default_checker is None:
                self._default_checker = await self._compile_checker()
            return self._default_checker
        else:
            file_id = self._spj_checkers.get(problem_id)
            if file_id is None:
                file_id = await self._compile_checker(problem_id)
                self._spj_checkers[problem_id] = file_id
            return file_id
            
