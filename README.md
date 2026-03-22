# XY-JudgeCore

基于 Redis Stream 与 go-judge 的高性能异步判题 Worker。

***

## 核心优势

### 一、架构解耦，即插即用

JudgeWorker 作为独立服务运行，与业务系统完全解耦：

```
┌─────────────┐      Redis Stream      ┌─────────────────────────────────┐
│   任意后端   │ ◀──────────────────▶ │          JudgeWorker 集群        │
│  (业务系统)  │      judge:tasks      │  ┌─────────┐ ┌─────────┐        │
│             │      judge:results     │  │ Worker1 │ │ Worker2 │ ...    │
└─────────────┘                        │  └─────────┘ └─────────┘        │
                                       │       ↓           ↓             │
                                       │    go-judge    go-judge         │
                                       └─────────────────────────────────┘
```

**集成只需一个 Redis Stream**：

- 后端往 `judge:tasks` 推送判题任务
- JudgeWorker 向 `judge:results` 推送判题结果
- 无需任何 API 调用、无需共享数据库、无需直接通信

**水平扩展，按需伸缩**：

- **Pull 模式主动拉取**：Worker 主动从队列拉取任务，根据自身处理能力决定消费速度
- **天然负载均衡**：处理快的 Worker 消费更多任务，无需后端调度算法
- **高峰期扩容**：增加 Worker 实例即可提升处理能力
- **低峰期缩容**：减少实例节省资源
- **故障自动接管**：单个 Worker 故障不影响整体服务，其他实例通过 XAUTOCLAIM 接管超时任务

这意味着：

- 可以用任何语言开发后端（Python/Go/Java/Node.js...）
- 可以随时增减 Worker 实例，无需修改后端代码
- 后端升级不影响判题服务，反之亦然

### 二、高并发异步架构

采用全异步 I/O 设计，单进程即可高效处理大量并发请求：

- **并发控制**：通过信号量精确控制并发度，避免资源过载
- **HTTP/2 多路复用**：与沙箱引擎通信使用 HTTP/2，减少连接开销
- **测试点并行**：同一提交的多个测试点并发执行，最大化吞吐量

### 三、生产级可靠性

基于 Redis Stream 消费组实现分布式任务调度：

| 机制         | 作用                             |
| ---------- | ------------------------------ |
| PEL 恢复     | Worker 重启后自动恢复未完成任务            |
| XAUTOCLAIM | 自动接管其他 Worker 的超时任务，实现故障转移     |
| 死信队列       | 重试超过 3 次的任务转入 DLQ，防止无限重试       |
| 原子操作       | 结果写入、ACK、删除使用 Pipeline 事务保证一致性 |

### 四、智能资源保护

自适应的系统资源监控策略：

- **PSI 模式**（Kernel ≥ 4.20）：通过 `/proc/pressure/` 获取精准的系统压力指标
- **传统模式**（Kernel < 4.20）：通过 `/proc/stat` 和 `/proc/meminfo` 检测 CPU/内存使用率

当系统负载超过阈值时自动暂停拉取新任务，防止服务器过载。

### 五、安全的沙箱隔离

基于 go-judge 实现容器级隔离：

- **资源限制**：CPU 时间、内存、进程数、输出大小全方位限制
- **文件隔离**：每次判题使用独立容器，自动清理缓存文件
- **Pipe 直连**：用户程序输出直接 pipe 到 Checker，高效比对

### 六、高性能答案比对

内置 C++ 实现的 Checker：

- **双模式**：严格模式（精确匹配）/ 宽松模式（忽略首尾空格和空行）
- **实时 OLE 检测**：读取时检查输出大小，超限立即终止
- **跨平台兼容**：自动处理 Windows/Linux 换行符差异
- **极致性能**：O2 编译，平均比对耗时 < 1ms

### 七、判题幂等性

实测数据证明判题结果高度稳定：

| 负载场景 | 平均耗时   | 耗时波动   | 平均内存    |
| ---- | ------ | ------ | ------- |
| 低负载  | 190.95 | ±10.85 | 10.3 MB |
| 中负载  | 191.10 | ±6.55  | 10.4 MB |
| 高负载  | 191.39 | ±7.80  | 10.4 MB |

***

## 快速集成

### 任务格式（推送到 judge:tasks）

```json
{
  "task": {
    "solution_id": 1,
    "language": 5,
    "src": "#include...",
    "max_cpu_time": 1000,
    "max_memory": 256,
    "problem_id": 100,
    "output": false,
    "is_spj": false,
    "ignore_space": false
  }
}
```

### 结果格式（从 judge:results 读取）

```json
{
  "result": {
    "solution_id": 1,
    "problem_id": 100,
    "result": 4,
    "time_ms": 190,
    "memory_kb": 10358,
    "pass_rate": 10000,
    "result_list": [
      {"case_id": 1, "case_result": 4, "time_ms": 50, "memory_kb": 8192},
      {"case_id": 2, "case_result": 4, "time_ms": 190, "memory_kb": 10358},
      {"case_id": 3, "case_result": 4, "time_ms": 120, "memory_kb": 9216}
    ],
    "message": null
  }
}
```

**详细结果支持多种赛制**：

- **ACM/ICPC**：根据最终结果判定通过/不通过
- **OI 赛制**：根据 `pass_rate` 计算部分分（如 7500 表示通过 75%）
- **IOI 赛制**：根据 `result_list` 获取每个测试点的得分

### 后端集成示例

```python
import redis
import json

r = redis.Redis()

# 提交判题任务
task = {
    "solution_id": 1,
    "language": 5,  # C++14
    "src": "#include <iostream>\nint main() { std::cout << 'Hello'; }",
    "max_cpu_time": 1000,
    "max_memory": 256,
    "problem_id": 100,
    "output": False,
    "is_spj": False,
    "ignore_space": False
}
r.xadd("judge:tasks", {"task": json.dumps(task)})

# 读取判题结果
results = r.xread({"judge:results": "0"}, count=1, block=10000)
```

***

## 模块结构

```
judgeworker/
├── worker.py        # 主循环，协调各组件
├── task.py          # 任务获取（PEL恢复/新任务/超时接管）
├── processor.py     # 任务处理（编译/运行/结果解析）
├── resource.py      # 资源监控（PSI优先/传统降级）
├── config.py        # 配置管理
├── languages.py     # 语言配置
├── result.py        # 结果定义
├── checker.cpp      # 答案比对器
└── gojudge/
    ├── client.py    # 沙箱通信客户端
    └── schemas.py   # API 数据模型
```

***

## 支持语言

| ID | 语言     | 编译器/解释器      | 编译时限 | 内存限制  |
| -- | ------ | -------------- | ---- | ----- |
| 0  | C99    | gcc            | 3s   | 256MB |
| 1  | C11    | gcc            | 3s   | 256MB |
| 2  | C17    | gcc            | 3s   | 256MB |
| 3  | C23    | gcc            | 3s   | 256MB |
| 4  | C++11  | g++            | 10s  | 512MB |
| 5  | C++14  | g++            | 10s  | 512MB |
| 6  | C++17  | g++            | 10s  | 512MB |
| 7  | C++20  | g++            | 10s  | 512MB |
| 8  | C++23  | g++            | 10s  | 512MB |
| 9  | Java   | javac          | 15s  | 1GB   |
| 10 | Go     | go build       | 15s  | 512MB |
| 11 | Rust   | rustc          | 20s  | 1GB   |
| 12 | Python3| python3        | -    | 128MB |
| 13 | NodeJS | node           | -    | 128MB |

***

## 判题状态

| 状态码 | 状态                    | 说明    |
| --- | --------------------- | ----- |
| 4   | Accepted              | 通过    |
| 5   | Presentation Error    | 格式错误  |
| 6   | Wrong Answer          | 答案错误  |
| 7   | Time Limit Exceeded   | 时间超限  |
| 8   | Memory Limit Exceeded | 内存超限  |
| 9   | Output Limit Exceeded | 输出超限  |
| 10  | Runtime Error         | 运行时错误 |
| 11  | Compile Error         | 编译错误  |
| 12  | System Error          | 系统错误  |

***

## 配置项

| 环境变量                               | 默认值                     | 说明         |
| ---------------------------------- | ----------------------- | ---------- |
| REDIS\_URL                         | redis\://localhost:6379 | Redis 地址   |
| JUDGE\_WORKER\_NAME                | worker-1                | Worker 名称  |
| JUDGE\_WORKER\_CONCURRENCY         | 10                      | 并发数        |
| JUDGE\_WORKER\_MAX\_SERVER\_CPU    | 85                      | CPU 阈值 (%) |
| JUDGE\_WORKER\_MAX\_SERVER\_MEMORY | 85                      | 内存阈值 (%)   |
| TEST\_CASE\_DIR                    | ./test\_case            | 测试用例目录     |
| GOJUDGE\_URL                       | <http://localhost:5050> | 沙箱地址       |

***

## 快速开始

```bash
# 安装依赖
pip install redis pydantic pydantic-settings httpx

# 编译 Checker
g++ checker.cpp -o checker -O2 -std=c++17

# 启动
python -m judgeworker.worker
```

***

## 依赖

- Python ≥ 3.12
- Redis ≥ 5.0
- [go-judge](https://github.com/criyle/go-judge)
- Linux Kernel ≥ 4.20（推荐，支持 PSI）

***

## 许可证

MIT License

Copyright (c) 2026 响滩

***

## 致谢

本项目基于 [go-judge](https://github.com/criyle/go-judge) 沙箱引擎实现，感谢作者提供的优秀开源项目。
