from redis_client import redis_client
import logging
import socket
from config import settings
from pydantic import BaseModel,Field,ValidationError
from languages import Language
import time
#如果使用docker需要处理proc的挂载，只读挂载
#内核大于4.20 优先使用psi作为负载指标
# 配置日志
logger = logging.getLogger(__name__)



#TODO:
#1 实现启动后先解决pel中的task，用于处理意外重启的情况
#2 实现xautoclaim机制，用于掠夺其余worker发生意外没能完成的任务，还需要看传递次数超过3次直接ack
#3 实现与gojudge的通信
#4 mvp 实现c/c++的普通判题
#5  Worker总体调度 ResourceManager检查系统资源 TaskFetcher 从redis拉取任务，自己维护状态
#先拉取自己的pel，然后拉取新的消息，定时拉取超时消息进行claim TaskProcessor 负责具体的与gojudge通信，执行判题


class JudgeTask(BaseModel):
    solution_id: int
    language: Language
    src: str
    max_cpu_time: int =Field(ge=1,le=15*1000) # 毫秒
    max_memory: int =Field(ge=1,le=2*1024) # mb 
    problem_id: int
    output: bool
    is_spj: bool
    ignore_space : bool #需要转换成checker的mode 1 宽松 2 严格
  


class TaskFetcher:
    """
    三个私有函数分别用于返回pel,new,claim的task 返回格式统一为tuple[str,JudgeTask|None]|tuple[None,None]如果task为non会自动xack
    fetch_one 返回msg_id,task worker需要判断两者均非空才去处理
    """
    def __init__(self):
        self.last_claim_time = 0
        self.has_pending_tasks = True
        self.STREAM = "judge:tasks"
        self.DLQ = "judge:tasks:dead"
        self.GROUP = "judge-workers"
        self.CONSUMER = settings.judge_worker_name
        self.CONSUMER_NAME = f"{self.CONSUMER}-{socket.gethostname()}"
        self.MIN_IDLE_TIME = settings.judge_worker_pending_idle_ms
        self.BLOCK_MS = settings.judge_worker_block_ms
        self._initialized = False


    async def _task_parser(self,msg_id,task_data:dict)->JudgeTask|None:
        raw_task = task_data.get("task")
        if not raw_task:
            logger.error(f"消息 {msg_id} 缺少 'task' 字段")
            async with redis_client.pipeline() as pipe:
                pipe.xadd(self.DLQ,{
                    "origin_msg_id":msg_id,
                    "origin_data":str(task_data),
                    "reason":"缺少task字段无法解析",
                    "worker":self.CONSUMER_NAME
                })
                pipe.xack(self.STREAM,self.GROUP,msg_id)
                pipe.xdel(self.STREAM,msg_id)
                await pipe.execute()
            
            return None
        try:
            task = JudgeTask.model_validate_json(raw_task)
            return task
        except ValidationError as e:
            logger.error(f"消息:{msg_id} 校验失败,请检查是否缺少参数或参数范围不合理,异常信息:{e}")
        except Exception as e:
            logger.error(f"消息{msg_id}json解析失败:{e}")
            
        async with redis_client.pipeline() as pipe:
            pipe.xadd(self.DLQ,{
                "origin_msg_id":msg_id,
                "origin_data":str(raw_task),
                "reason":f"JSON解析失败:{str(e)}",
                "worker":self.CONSUMER_NAME
            })
            pipe.xack(self.STREAM,self.GROUP,msg_id)
            pipe.xdel(self.STREAM,msg_id)
            await pipe.execute()
        return None

    async def _fetch_from_pel(self)->tuple[str,JudgeTask]|tuple[None,None]:
        """
        处理自己的Pending队列(ID='0'),用于启动后完成因意外关闭导致未ack的任务
        """
        # 格式: [{'message_id': '1001-0', 'consumer': 'worker_1', 'idle': 5000, 'times_delivered': 3}]
        #xpending_range查询的是元数据不包含原始数据，xrange可以查具体的数据，此处先查出id判断传递次数再查内容
        pending_list = await redis_client.xpending_range(
            self.STREAM,self.GROUP,min='-',max='+',count=1,consumername=self.CONSUMER_NAME
        )
        if not pending_list:return None,None

        msg_id = pending_list[0]['message_id']
        delivery_count = pending_list[0]['times_delivered']

        # XRANGE 格式: [(msg_id, {key1: val1, key2: val2, ...}), ...]
        #根据查到的id去拿任务确保可靠性
        data_list = await redis_client.xrange(self.STREAM,min=msg_id,max=msg_id)
        if not data_list:
            return None,None
        
        msg_id,data  = data_list[0]

        if delivery_count > 3:
            logger.error(f"PEL任务{msg_id} 重试次数过多({delivery_count}),自动执行ack,放入死信队列:judge:tasks:dead")
            async with redis_client.pipeline() as pipe:
                pipe.xadd(self.DLQ,{
                    "origin_msg_id":msg_id,
                    "task":data.get("task"),
                    "reason":"尝试次数过多",
                    "worker":self.CONSUMER_NAME,
                    "retry_count":delivery_count
                })
                pipe.xack(self.STREAM,self.GROUP,msg_id)
                pipe.xdel(self.STREAM,msg_id)
                await pipe.execute()
            return None,None
        

        task = await self._task_parser(msg_id,data)
        if not task:
            return None,None
        return msg_id,task
        
    async def _fetch_by_claim(self)->tuple[str,JudgeTask]|tuple[None,None]:
        """
        自动掠夺其余worker的超时任务
        """
        result = await redis_client.xautoclaim(
            name = self.STREAM,
            groupname = self.GROUP,
            consumername= self.CONSUMER_NAME,
            min_idle_time = self.MIN_IDLE_TIME,
            start_id="0-0",
            count=1
        )#先claim获得归属权然后再去查传递次数决定是否丢进死信队列
        # xautoclaim 的返回格式比较特殊: (next_id, [messages], [deleted_ids])
        if not(result and result[1]):
            #清理 result[2] 里的 deleted_ids
            if result and result[2]:
                await redis_client.xack(self.STREAM,self.GROUP,*result[2])
            return None,None


        msg_id,data = result[1][0]
        pending_list = await redis_client.xpending_range(
            self.STREAM,self.GROUP,min=msg_id,max=msg_id,count=1
        )
        
        if pending_list and pending_list[0]['times_delivered'] > 3:
            logger.error(f"claim任务{msg_id}尝试次数过多已ack")
            async with redis_client.pipeline() as pipe:
                pipe.xadd(self.DLQ,{
                    "origin_msg_id":msg_id,
                    "task":data.get("task"),
                    "reason":"尝试次数过多",
                    "worker":self.CONSUMER_NAME,
                    "retry_count":pending_list[0]['times_delivered']
                })
                pipe.xack(self.STREAM,self.GROUP,msg_id)
                pipe.xdel(self.STREAM,msg_id)
                await pipe.execute()

            return None,None
        task = await self._task_parser(msg_id,data)
        if not task:
            return None,None
        return msg_id,task

        

    async def _fetch_new(self)->tuple[str,JudgeTask]|tuple[None,None]:
        result = await redis_client.xreadgroup(
                    groupname=self.GROUP,
                    consumername=self.CONSUMER_NAME,
                    streams={self.STREAM: ">"},
                    count=1,
                    block=self.BLOCK_MS
                )
        if not result : return None,None
        # 格式通常是: [[stream_name, [(msg_id, data_dict)]]]
        _,messages = result[0]
        msg_id,data = messages[0]
        task = await self._task_parser(msg_id,data)
        if not task:
            return None,None
        return msg_id,task
    
  
    async def _setup(self):
        try:
            # '0' 表示从头开始读取。
            await redis_client.xgroup_create(self.STREAM, self.GROUP, id="0", mkstream=True)
            logger.info(f"已为流 {self.STREAM} 创建消费组 {self.GROUP}")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"消费组 {self.GROUP} 已存在")
            else:
                logger.error(f"创建消费组出错: {e}")

        self._initialized = True

    async def fetch_one(self)->tuple[str,JudgeTask]|tuple[None,None]:        
        if not self._initialized:
            await self._setup()

        if self.has_pending_tasks:
            msg_id,task = await self._fetch_from_pel()
            if msg_id and task: return msg_id,task
            self.has_pending_tasks = False

        now = time.time()
        if now - self.last_claim_time > 30:
            msg_id,task = await self._fetch_by_claim()
            if msg_id and task: return msg_id,task
            self.last_claim_time = now#如果有claim任务就一直claim直到处理完所有任务

        return await self._fetch_new()



