# XY-JudgeCore

A high-performance asynchronous judging worker based on Redis Stream and go-judge.

***

## Key Features

### 1. Decoupled Architecture, Plug and Play

JudgeWorker runs as an independent service, fully decoupled from the business system:

```
┌─────────────┐      Redis Stream      ┌─────────────────────────────────┐
│   Backend   │ ◀──────────────────▶ │        JudgeWorker Cluster       │
│  (Any Lang) │      judge:tasks      │  ┌─────────┐ ┌─────────┐        │
│             │      judge:results     │  │ Worker1 │ │ Worker2 │ ...    │
└─────────────┘                        │  └─────────┘ └─────────┘        │
                                       │       ↓           ↓             │
                                       │    go-judge    go-judge         │
                                       └─────────────────────────────────┘
```

**Integration requires only a Redis Stream**:

- Backend pushes tasks to `judge:tasks`
- JudgeWorker writes results to `judge:results`
- No API calls, no shared database, no direct communication

**Horizontal Scaling**:

- **Pull Mode**: Workers actively pull tasks, consuming at their own pace
- **Natural Load Balancing**: Faster workers consume more tasks, no backend scheduling needed
- **Scale Up**: Add worker instances during peak hours
- **Scale Down**: Remove instances during low traffic
- **Auto Failover**: XAUTOCLAIM allows other workers to take over timed-out tasks

This means:

- Backend can be developed in any language (Python/Go/Java/Node.js...)
- Add or remove workers anytime without modifying backend code
- Backend upgrades don't affect judging service, and vice versa

### 2. High-Concurrency Async Architecture

Fully async I/O design, single process handles massive concurrent requests:

- **Concurrency Control**: Semaphore-based precise control to avoid resource overload
- **HTTP/2 Multiplexing**: HTTP/2 communication with sandbox engine reduces connection overhead
- **Parallel Test Cases**: Multiple test cases of the same submission run in parallel

### 3. Production-Grade Reliability

Distributed task scheduling based on Redis Stream consumer groups:

| Mechanism    | Description                                    |
| ------------ | ---------------------------------------------- |
| PEL Recovery | Auto-recover unfinished tasks after restart    |
| XAUTOCLAIM   | Auto-claim timed-out tasks from other workers  |
| Dead Letter  | Tasks with 3+ retries go to DLQ                |
| Atomic Ops   | Pipeline transactions ensure consistency       |

### 4. Smart Resource Protection

Adaptive system resource monitoring:

- **PSI Mode** (Kernel ≥ 4.20): Precise pressure metrics via `/proc/pressure/`
- **Legacy Mode** (Kernel < 4.20): CPU/memory detection via `/proc/stat` and `/proc/meminfo`

Automatically pauses task fetching when system load exceeds threshold.

### 5. Secure Sandbox Isolation

Container-level isolation based on go-judge:

- **Resource Limits**: CPU time, memory, process count, output size
- **File Isolation**: Each judgment uses an isolated container
- **Pipe Direct**: User program output pipes directly to Checker

### 6. High-Performance Answer Comparison

Built-in C++ Checker:

- **Dual Mode**: Strict mode / Relaxed mode (ignores trailing spaces and empty lines)
- **Real-time OLE Detection**: Terminates immediately when output exceeds limit
- **Cross-platform**: Handles Windows/Linux line ending differences
- **Extreme Performance**: O2 compiled, average comparison time < 1ms

### 7. Judging Idempotency

Test data proves highly stable results:

| Load Scenario | Avg Time (ms) | Time Variance | Avg Memory |
| ------------- | ------------- | ------------- | ---------- |
| Low           | 190.95        | ±10.85        | 10.3 MB    |
| Medium        | 191.10        | ±6.55         | 10.4 MB    |
| High          | 191.39        | ±7.80         | 10.4 MB    |

***

## Quick Integration

### Task Format (push to judge:tasks)

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

### Result Format (read from judge:results)

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

**Detailed results support multiple contest formats**:

- **ACM/ICPC**: Pass/fail based on final result
- **OI Format**: Partial scores via `pass_rate` (e.g., 7500 = 75% passed)
- **IOI Format**: Individual test case scores via `result_list`

  <br />

### Backend Integration Example

```python
import redis
import json

r = redis.Redis()

# Submit judging task
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

# Read judging result
results = r.xread({"judge:results": "0"}, count=1, block=10000)
```

***

## Module Structure

```
judgeworker/
├── worker.py        # Main loop, coordinates components
├── task.py          # Task fetching (PEL recovery/new tasks/timeout claim)
├── processor.py     # Task processing (compile/run/parse results)
├── resource.py      # Resource monitoring (PSI priority/legacy fallback)
├── config.py        # Configuration management
├── languages.py     # Language configs
├── result.py        # Result definitions
├── checker.cpp      # Answer comparator
└── gojudge/
    ├── client.py    # Sandbox communication client
    └── schemas.py   # API data models
```

***

## Supported Languages

| ID | Language | Compiler/Interpreter | Compile Limit | Memory Limit |
| -- | -------- | -------------------- | ------------- | ------------ |
| 0  | C99      | gcc                  | 3s            | 256MB        |
| 1  | C11      | gcc                  | 3s            | 256MB        |
| 2  | C17      | gcc                  | 3s            | 256MB        |
| 3  | C23      | gcc                  | 3s            | 256MB        |
| 4  | C++11    | g++                  | 10s           | 512MB        |
| 5  | C++14    | g++                  | 10s           | 512MB        |
| 6  | C++17    | g++                  | 10s           | 512MB        |
| 7  | C++20    | g++                  | 10s           | 512MB        |
| 8  | C++23    | g++                  | 10s           | 512MB        |
| 9  | Java     | javac                | 15s           | 1GB          |
| 10 | Go       | go build             | 15s           | 512MB        |
| 11 | Rust     | rustc                | 20s           | 1GB          |
| 12 | Python3  | python3              | -             | 128MB        |
| 13 | NodeJS   | node                 | -             | 128MB        |

***

## Judge Status

| Code | Status                | Description        |
| ---- | --------------------- | ------------------ |
| 4    | Accepted              | Passed             |
| 5    | Presentation Error    | Format error       |
| 6    | Wrong Answer          | Wrong answer       |
| 7    | Time Limit Exceeded   | Time limit exceeded|
| 8    | Memory Limit Exceeded | Memory limit exceeded |
| 9    | Output Limit Exceeded | Output limit exceeded |
| 10   | Runtime Error         | Runtime error      |
| 11   | Compile Error         | Compile error      |
| 12   | System Error          | System error       |

***

## Configuration

| Environment Variable                | Default                   | Description        |
| ----------------------------------- | ------------------------- | ------------------ |
| REDIS_URL                           | redis://localhost:6379    | Redis address      |
| JUDGE_WORKER_NAME                   | worker-1                  | Worker name        |
| JUDGE_WORKER_CONCURRENCY            | 10                        | Concurrency        |
| JUDGE_WORKER_MAX_SERVER_CPU         | 85                        | CPU threshold (%)  |
| JUDGE_WORKER_MAX_SERVER_MEMORY      | 85                        | Memory threshold (%)|
| TEST_CASE_DIR                       | ./test_case               | Test case directory|
| GOJUDGE_URL                         | http://localhost:5050     | Sandbox address    |

***

## Quick Start

```bash
# Install dependencies
pip install redis pydantic pydantic-settings httpx

# Compile Checker
g++ checker.cpp -o checker -O2 -std=c++17

# Start
python -m judgeworker.worker
```

***

## Dependencies

- Python ≥ 3.12
- Redis ≥ 5.0
- [go-judge](https://github.com/criyle/go-judge)
- Linux Kernel ≥ 4.20 (recommended, for PSI support)

***

## License

MIT License

Copyright (c) 2026 响滩

***

## Acknowledgements

This project is built on [go-judge](https://github.com/criyle/go-judge) sandbox engine. Many thanks to the author for this excellent open-source project.
