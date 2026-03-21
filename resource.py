import logging
import asyncio
from .config import settings

MAX_SERVER_CPU = settings.judge_worker_max_server_cpu
MAX_SERVER_MEMORY = settings.judge_worker_max_server_memory
logger = logging.getLogger(__name__)

class ResourceManager:
    def __init__(self) -> None:
        self.last_cpu_stats = None
        self.psi_available  = None

    def _read_cpu_stats(self):
        """读取 /proc/stat 并返回 (total, idle) ticks。"""
        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline()
            # cpu  user nice system idle iowait irq softirq steal guest guest_nice
            parts = line.split()[1:]
            values = [int(x) for x in parts]
            # idle = idle + iowait
            idle = values[3] + values[4]
            total = sum(values)
            return total, idle
        except Exception as e:
            logger.error(f"读取 CPU 统计信息出错: {e}")
            return 0, 0
    
    def _read_psi_value(self, file_path: str) -> float:
        """解析 PSI 文件中的 some avg10 值。"""
        # 格式: some avg10=0.00 avg60=0.00 avg300=0.00 total=0
        with open(file_path, 'r') as f:
            content = f.readline()
            parts = content.split()
            for part in parts:
                if part.startswith("avg10="):
                    return float(part.split("=")[1])
        return 0.0

    def check_legacy_resources(self) -> bool:
        """使用 /proc 检查系统资源（传统百分比方式）。如果正常返回 True。"""
        # 1. 内存检查
        try:
            mem_total = 0
            mem_available = 0
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        mem_total = int(line.split()[1])
                    elif line.startswith('MemAvailable:'):
                        mem_available = int(line.split()[1])
                    if mem_total and mem_available:
                        break
            
            if mem_total > 0:
                mem_usage = 100 * (1 - mem_available / mem_total)
                if mem_usage > MAX_SERVER_MEMORY:
                    logger.warning(f"内存使用率过高: {mem_usage:.1f}%. 暂停拉取任务。")
                    return False
        except Exception as e:
            logger.error(f"读取内存统计信息出错: {e}")
        
        # 2. CPU 检查
        current_total, current_idle = self._read_cpu_stats()
        
        if self.last_cpu_stats is None:
            self.last_cpu_stats = (current_total, current_idle)
            # 第一次运行，没有增量数据，默认正常
            return True
            
        prev_total, prev_idle = self.last_cpu_stats
        self.last_cpu_stats = (current_total, current_idle)
        
        delta_total = current_total - prev_total
        delta_idle = current_idle - prev_idle
        
        if delta_total > 0:
            cpu_usage = 100 * (1 - delta_idle / delta_total)
            if cpu_usage > MAX_SERVER_CPU:
                logger.warning(f"CPU 使用率过高: {cpu_usage:.1f}%. 暂停拉取任务。")
                return False
        
        return True


    async def wait_for_resources(self):
        """
        智能资源等待策略。
        优先使用 PSI (Pressure Stall Information) 进行精准限流。
        如果 PSI 不可用，降级到传统的 CPU/内存百分比阈值检测。
        """
        # 尝试 PSI 逻辑
        while True:
            if self.psi_available is not False:
                try:
                    # 检查 CPU 压力
                    cpu_avg10 = self._read_psi_value('/proc/pressure/cpu')
                    # 检查 内存 压力
                    mem_avg10 = self._read_psi_value('/proc/pressure/memory')
            
                    self.psi_available = True
                    
                    if cpu_avg10 <=20.0 and mem_avg10 <=10.0:
                        return 
                    
                    logger.warning(f"PSI 过载 (CPU:{cpu_avg10:.2f}, MEM:{mem_avg10:.2f})，等待中...")
                except FileNotFoundError:
                    if self.psi_available is None:
                        logger.warning("未检测到 PSI 支持 (Kernel < 4.20?)，降级到传统百分比检测模式。")
                    self.psi_available = False
                except Exception as e:
                    logger.error(f"PSI 读取异常: {e}，降级处理。")
                    self.psi_available = False
                
            else:
                if  self.check_legacy_resources():
                    return
            
            await asyncio.sleep(1.0)
