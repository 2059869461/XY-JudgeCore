from __future__ import annotations
import logging
import asyncio
from pathlib import Path

from .gojudge.client import GoJudgeClient, TaskContext
from .gojudge.schemas import *
from .languages import get_language_config,Language
from .task import JudgeTask
from .result import JudgeResult, JudgeStatus, CaseResult
import json
from .gojudge.client import SandboxErrorBase
from .config import settings
from .checker import CheckerCompileError
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .checker import CheckerManager
logger = logging.getLogger(__name__)
"""
需要实现 1.checker提前编译缓存在gojudge内部，这个应该由worker初始化的时候负责，获得文件ID,另外可考虑编译好后直接挂载入gojudge
2. 解析task 尤其是语言映射成对应语言的配置，然后构造request 发送给gojudge，解析response，转换成JudgeResult，并返回入redis judge:results 流，后端收到后进行xack
3. processor 需要实现利用GoJudgeClient与gojudge的交互，利用TaskContext自动管理缓存文件的生命期，将JudgeTask转换成request，控制测试点的并发问题
JudgeTask -> GoJugdeRequest 
GoJudge 使用“容器池”技术，粒度是“一个 Cmd 一个容器”。
内部缓冲队列大小512
GoJudge 同一个request中的不同cmd会尝试并发执行而不是串行
根据测试 使用异步并发逐个测试点发过去在gojudge与worker在同机器上性能略微优于一次性构造一个大的request发送过去
"""
"""
TODO:
    run测试点的时候构造一个request包含两个cmd，同时运行checker和用户代码，通过pipe直接连接，checker发现不一致直接杀死用户代码然后返回
    - 方案 A：如果需要展示，可以在 Checker 的 files 中对 stdin 开启 proxy: true （go-judge 特性），这样 go-judge 会帮你 copy 一份数据出来。
- 方案 B：Checker 的 stderr 通常会打印 wrong answer expecting '3', found '4' ，这通常足够了。

需要转为预编译checker,减少每次从磁盘启动的时间,考虑路径拼接问题,以及去除硬编码路径
"""
class SandboxRunError(SandboxErrorBase):
    pass
class InvalidLanguage(Exception):
    pass
class TaskProcessor:
    def __init__(self,client:GoJudgeClient,checker_manager:CheckerManager|None=None) -> None:
        self.client = client
        self.checker_manager = checker_manager
    async def compile(self,language:int,src:str,ctx:TaskContext,)->tuple[bool,str]:
        """
        
        Returns:
            tuple[bool, str]: 返回一个元组 (success, result)。sucess代表编译是否通过,如果通过str是fileId,不通过是stderr
        Raises:
            InvalidLanguage: 非法语言
            SandboxRunError: 沙箱运行出错
        非编译语言如python也会进行一次语法检查,如果错误返回false认定为CE
        """
        try:
            language_config = get_language_config(language)
        except ValueError:
            raise InvalidLanguage(f"不支持的语言:{language}")
        if language_config.compile_args is None: #非编译的语言直接上传文件然后返回
            file_id  = await ctx.upload_file(name=language_config.exe_name,content=src)
            return True,file_id
        cmd = Cmd(
            args = language_config.compile_args,
            env = language_config.env,
            cpuLimit=language_config.compile_cpu_time,
            clockLimit=language_config.compile_cpu_time*3,
            memoryLimit=language_config.compile_memory,
            procLimit=50,
            copyIn={
                language_config.src_name:MemoryFile(content=src)
            },
            copyOut=["stdout","stderr"],
            copyOutCached=[language_config.exe_name],
            files=[
                MemoryFile(content=""),
                Collector(name="stdout",max=8*1024),
                Collector(name="stderr",max=8*1024)
            ]
        )

        go_request = Request(cmd=[cmd])
        results = await ctx.run_task(go_request)

        
        result = results[0]
        if result.status!=Status.Accepted :
            return False,result.files.get("stderr")
        if not result.fileIds:
            raise SandboxRunError("未找到编译后的文件id")
        file_id = result.fileIds.get(language_config.exe_name)#需要修改
        if  not file_id:
            raise SandboxRunError("未找到编译后的文件id")
        await ctx.register_file(file_id)
        return True,file_id

        
    async def _parse_result(self,test_case_id:int,run_result:Result,checker_result:Result)->CaseResult:
        """
        内部错误提前退出 （比如文件打开失败），也会提前关闭 pipe，这种情况下用户进程同样可能收到 SIGPIPE，但这与 WA 逻辑无关。
        """
        logger.info(run_result.model_dump_json())
        logger.info(checker_result.model_dump_json())
        status = JudgeStatus.SYSTEM_ERROR
        if run_result.status == Status.TimeLimitExceeded:
            status = JudgeStatus.TIME_LIMIT_EXCEEDED
        elif run_result.status == Status.MemoryLimitExceeded:
            status = JudgeStatus.MEMORY_LIMIT_EXCEEDED
        elif run_result.status == Status.OutputLimitExceeded:
            status = JudgeStatus.OUTPUT_LIMIT_EXCEEDED
        elif run_result.status == Status.NonzeroExitStatus or run_result.status == Status.Signalled:
            if checker_result.exitStatus==3 and checker_result.status == Status.NonzeroExitStatus:
                status = JudgeStatus.OUTPUT_LIMIT_EXCEEDED 
                #pipe 把用户程序 stdout 直接喂给 checker（ processor.py ）。
                # 当 checker 检测到 OLE 提前退出 后，pipe 读端关闭，用户程序继续写 stdout 会触发 SIGPIPE ，
                # 默认行为是进程被信号杀死。因此需要专门判断
                #此处两个分支均是为了判断如果checker先退出,导致用户代码signalled的逻辑
            elif checker_result.exitStatus ==4 and checker_result.status == Status.NonzeroExitStatus:
                status = JudgeStatus.SYSTEM_ERROR
                raise SandboxRunError(f"checker内部错误:用户代码运行结果:{run_result.model_dump_json()},checker运行结果:{checker_result.model_dump_json()}")
            else:
                status = JudgeStatus.RUNTIME_ERROR
        elif run_result.status == Status.Accepted:
            if checker_result.exitStatus == 0 and checker_result.status==Status.Accepted:
                status = JudgeStatus.ACCEPTED
            elif checker_result.exitStatus == 1 and checker_result.status==Status.NonzeroExitStatus:
                status = JudgeStatus.PRESENTATION_ERROR
            elif checker_result.exitStatus == 2 and checker_result.status==Status.NonzeroExitStatus:
                status = JudgeStatus.WRONG_ANSWER
            elif checker_result.exitStatus == 3 and checker_result.status==Status.NonzeroExitStatus:
                status = JudgeStatus.OUTPUT_LIMIT_EXCEEDED
            elif checker_result.exitStatus == 4 and checker_result.status == Status.NonzeroExitStatus:
                status = JudgeStatus.SYSTEM_ERROR
                raise SandboxRunError(f"checker内部错误:用户代码运行结果:{run_result.model_dump_json()},checker运行结果:{checker_result.model_dump_json()}")
            else:
                raise SandboxRunError(f"checker内部错误:{checker_result.model_dump_json()}")
        elif run_result.status == Status.FileError:
            raise SandboxRunError(f"沙箱内部File Error:{run_result.model_dump_json()}")
        elif run_result.status == Status.InternalError:
            raise SandboxRunError(f"沙箱内部错误InternalError:{run_result.model_dump_json()}")
        else:
            raise SandboxRunError("沙箱File Error或 Sandbox Internal Error")
        return CaseResult(
            case_id=test_case_id,
            case_result=status,
            time_ms=run_result.time //1000 //1000,
            memory_kb=run_result.memory //1024
        )            

    async def run(self,test_case_id:int,test_case_path:str,mode:int,cpu_limit:int,memory_limit:int,language:int,file_id:str,ctx:TaskContext,spj:bool=False,problem_id:int|None=None)->CaseResult:  
        language_config = get_language_config(language)
        cpu_limit = cpu_limit * 1000 * 1000 #ms -> ns
        memory_limit = memory_limit * 1024 * 1024#mb -> b
        cmd_run = Cmd(
            args=language_config.run_args,
            env=language_config.env,
            files=[
                LocalFile(src=test_case_path+".in"),
                None,
                Collector(name="stderr",max=4*1024)
            ],
            cpuLimit=cpu_limit,
            clockLimit=cpu_limit * 3,
            memoryLimit= memory_limit,
            procLimit= 50,
            copyIn={
                language_config.exe_name:PreparedFile(fileId=file_id),
                f"{test_case_id}.in":LocalFile(src=test_case_path+".in")
            }

        )
        checker_config = get_language_config(Language.CHECKER)
        assert self.checker_manager is not None
        if spj:
            checker_id =await  self.checker_manager.get_checker(problem_id=problem_id)
        else:
            checker_id = await self.checker_manager.get_checker()
        cmd_checker = Cmd(
            args=["./checker","input.in",f"{test_case_id}.out",str(mode)],
            env=checker_config.env,
            files=[
                None,
                Collector(name="checker_out",max=4096),
                Collector(name="checker_error",max=4096)
            ],
            cpuLimit=min(cpu_limit+2 * 1000 * 1000 * 1000,cpu_limit*3),#运行时间略大于用户程序
            clockLimit=cpu_limit  * 3,#墙上时钟与用户进程相同
            memoryLimit=checker_config.compile_memory,
            procLimit=50,
            copyIn={
                "input.in":MemoryFile(content=""),
                "checker":PreparedFile(fileId=checker_id),
                f"{test_case_id}.out":LocalFile(src=test_case_path+".out")
                #test_case_path:CmdFile(src=test_case_path),
            }
        )
        pipe = PipeMap(
            in_pos = PipeIndex(index=0,fd=1),
            out = PipeIndex(index=1,fd=0),
            #proxy=True,
        )#后续需要考虑proxy问题和max限制问题
        go_request = Request(
            cmd=[cmd_run,cmd_checker],
            pipeMapping=[pipe]
        )
        results = await ctx.run_task(go_request)
        run_result = results[0]
        checker_result = results[1]
        if run_result.error or checker_result.error:
            raise SandboxRunError(f"沙箱错误: 用户代码结果:{run_result.model_dump_json()};  checker运行结果:{checker_result.model_dump_json()}") 
        
        return await self._parse_result(test_case_id,run_result,checker_result)

    async def _get_testcase_config(self,problem_id:int):
        path = Path(settings.test_case_dir)/str(problem_id)/"info.json"
    
        with path.open("r",encoding='utf-8') as f:
            return json.load(f)
      
    async def _final_status(self,result:list[CaseResult])->JudgeStatus:
        fail_status = [case.case_result for case in result if case.case_result != JudgeStatus.ACCEPTED]
        if not fail_status:
            return JudgeStatus.ACCEPTED
        priority =[
            JudgeStatus.RUNTIME_ERROR,
            JudgeStatus.TIME_LIMIT_EXCEEDED,
            JudgeStatus.MEMORY_LIMIT_EXCEEDED,
            JudgeStatus.OUTPUT_LIMIT_EXCEEDED,
            JudgeStatus.WRONG_ANSWER,
            JudgeStatus.PRESENTATION_ERROR
        ]
        for p in priority:
            if p in fail_status:
                return p
        
        return fail_status[0] #如果没有找到默认返回第一个
    
    async def process(self,task:JudgeTask)->JudgeResult:
        try:
            async with self.client.task_context() as ctx:
                compile_ok,file_id = await self.compile(task.language,task.src,ctx)
                if not compile_ok:
                    return JudgeResult(
                        solution_id=task.solution_id,
                        problem_id=task.problem_id,
                        result=JudgeStatus.COMPILE_ERROR,
                        message=file_id,#如果失败返回False 第二个元素代表编译错误的stderr
                        pass_rate=0
                    )
                
                problem_config = await self._get_testcase_config(task.problem_id)
           
                if task.ignore_space:
                    mode = 1
                else:
                    mode = 2

                case_count = problem_config.get("case_count",0)
                coros = [ self.run(case_id,f"{settings.test_case_dir}/{task.problem_id}/{case_id}",
                                   mode,task.max_cpu_time,task.max_memory,
                                   task.language,file_id,ctx  
                                   ) for case_id in range(1,case_count+1)
                        ]
                result = await asyncio.gather(*coros)
                max_time = max( (c.time_ms for c in result),default=0 )
                max_memory = max((c.memory_kb for c in result) ,default=0)
                final_status = await self._final_status(result)
                ac_cnt = sum(1 for res in result if res.case_result == JudgeStatus.ACCEPTED)
                case_cnt = len(result)
                return JudgeResult(
                    solution_id=task.solution_id,
                    problem_id=task.problem_id,
                    result=final_status,
                    result_list=result,
                    time_ms=max_time,
                    memory_kb=max_memory,
                    pass_rate=int(ac_cnt *10000 //case_cnt )if case_cnt>0 else 0
                )
        #processor 只捕获无法重试的非沙箱异常，沙箱异常交给上层的process_task 协程处理
        except InvalidLanguage as e:
            logger.error(f"处理提交:{task.solution_id}过程出错:{e}")
        except FileNotFoundError:
            logger.error(f"处理提交:{task.solution_id}过程出错:找不到配置文件: {settings.test_case_dir}{task.problem_id}/info.json")
        except json.JSONDecodeError:
            logger.error(f"处理提交:{task.solution_id}过程出错:JSON格式错误，无法解析: {settings.test_case_dir}/{task.problem_id}/info.json")
        except PermissionError:
            logger.error(f"处理提交:{task.solution_id}过程出错:权限不足，无法读取文件: {settings.test_case_dir}/{task.problem_id}/info.json")
        except CheckerCompileError as e:
            if e.problem_id is None:
                logger.fatal(f"Checker 编译失败,无法进行判题,错误信息:{e}")
            else:
                logger.error(f"题目:{e.problem_id}的spj checker编译失败,错误信息:{e}")#后续可考虑主动掠过该题目的task,直到恢复

        return JudgeResult(
            solution_id=task.solution_id,
            problem_id=task.problem_id,
            result=JudgeStatus.SYSTEM_ERROR
        )
                

