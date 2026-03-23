from redis_client import redis_client
import asyncio
import logging
import socket
from config import settings
from resource_manager import ResourceManager
from task import JudgeTask,TaskFetcher
from processor import TaskProcessor
from gojudge.client import GoJudgeClient
from gojudge.client import SandboxErrorBase
from checker import  CheckerManager,CheckerCompileError
#如果使用docker需要处理proc的挂载，只读挂载
#内核大于4.20 优先使用psi作为负载指标
# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
"""
TODO:
    需要实现systemd的守护进程
    测试同一次提交的幂等性，耗时是否一致
    测试恶意代码是否能逃逸，是否有网络
    测试是否发生gojudge的内存泄漏，检查当前文件回收是否完备
    考虑是预编译checker还是每次初始化编译后获得fileid
    run:  python -m judgeworker.worker
    unshare (Mount Namespace) 或者 OverlayFS，让选手程序在运行期间看到的根目录完全是空的。
"""



class JudgeWorker:
    def __init__(self):
        self.CONCURRENCY = settings.judge_worker_concurrency
        self.semaphore = asyncio.Semaphore(self.CONCURRENCY)
        self.compute_semaphore = asyncio.Semaphore(self.CONCURRENCY)#计算用的信号量全局唯一
        self.running = True
        self.CONSUMER = settings.judge_worker_name
        self.CONSUMER_NAME = f"{self.CONSUMER}-{socket.gethostname()}"
        self.client = GoJudgeClient(compute_semaphore=self.compute_semaphore)#底层http连接池
        self.STREAM = "judge:tasks"
        self.GROUP = "judge-workers"
        self.fetcher = TaskFetcher()
        self.resource = ResourceManager()
        self.processor = TaskProcessor(client=self.client)
        self.checker_manager = None
        self.sandbox_ok = False

    async def wait_for_sandbox(self):
        """
        process_task 捕获异常后设置标志位,主循环会暂停进入等待沙箱恢复,避免无意义的重试
        """
        retry_cnt = 0
        while True:
            try:
                logger.info(f"判题沙箱出错正在进行第{retry_cnt}次重试")
                await self.client.request("GET","/version")
                logger.info("沙箱恢复成功,继续进行主循环")
                self.sandbox_ok = True
                break
            except Exception:
                await asyncio.sleep(min(2**retry_cnt,60))
                retry_cnt += 1
                if retry_cnt > 1e9:
                    retry_cnt = 60

    async def process_task(self, msg_id: str, task:JudgeTask, processor:TaskProcessor,semaphore: asyncio.Semaphore):
        """处理单个任务。必须在 finally 中释放信号量。"""
        try:


            logger.info(f"开始处理提交 {task.solution_id} (msg_id: {msg_id})")

            result = await processor.process(task)
            async with redis_client.pipeline(transaction=True) as pipe:
                pipe.xadd("judge:results",{"result":result.model_dump_json()})
                pipe.xack(self.STREAM,self.GROUP,msg_id)#进入结果流后直接xack,无需后端xack
                pipe.xdel(self.STREAM,msg_id)
                await pipe.execute()
            logger.info(f"提交 {task.solution_id} 处理完成")
        except SandboxErrorBase as e:
            if self.sandbox_ok:
                logger.error(f"判题沙箱出错:{e}")
                self.sandbox_ok = False
        except Exception as e:
            logger.error(f"处理任务 {msg_id} 时发生错误: {e}")
        finally:
            # 资源闭环：确保释放
            semaphore.release()

    async def run(self):
        logger.info(f"JudgeWorker {self.CONSUMER_NAME} 已启动。并发数: {self.CONCURRENCY}")
        
        # 初始化 CPU 统计（用于传统模式）
        self.resource.check_legacy_resources()
        async with self.client.task_context() as ctx:
            self.checker_manager = CheckerManager(ctx,self.client,processor=self.processor)
            self.processor.checker_manager = self.checker_manager
            while self.running:
                if not self.sandbox_ok:
                    await self.wait_for_sandbox()
                # 1. 信号量先行 (The Gatekeeper)，必须获取信号量之后才会进行，如果没有就挂起不占用资源
                await self.semaphore.acquire()

                try:

                    await self.resource.wait_for_resources()
                    msg_id,task = await self.fetcher.fetch_one()

                    if not msg_id or not task:#任意一个为空说明发生意外已经被taskfetcher ack掉了直接处理下一个
                        self.semaphore.release()
                        continue

                    asyncio.create_task(self.process_task(msg_id, task,self.processor, self.semaphore))
                    
                except Exception as e:
                    logger.error(f"主循环发生错误: {e}")
                    # 发生错误（如 Redis 连接断开），必须释放信号量
                    self.semaphore.release()
                    await asyncio.sleep(1)

if __name__ == "__main__":
    # 独立运行时配置基本日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    worker = JudgeWorker()
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        pass
