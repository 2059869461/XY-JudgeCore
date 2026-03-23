"""
judgeworker 测试基础设施
- 精确追踪 Redis 消息 ID
- 使用固定目录 /tmp/judgeworker_test_cases 存放测试用例
- 禁止删除 Redis 流，只使用 XACK + XDEL 清理特定消息
- 清理测试用例时只删除具体的 problem 目录，绝不删除父目录
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sys
from pathlib import Path

JUDGEWORKER_DIR = Path(__file__).resolve().parent.parent
if str(JUDGEWORKER_DIR) not in sys.path:
    sys.path.insert(0, str(JUDGEWORKER_DIR))

os.environ["TESTING"] = "1"
os.environ["TMP_TEST_CASE_DIR"] = "/tmp/judgeworker_test_cases"

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

import pytest

from config import settings
from task import JudgeTask
from result import JudgeResult, JudgeStatus
from languages import Language


TEST_CASE_DIR = Path(settings.test_case_dir)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def tracked_msg_ids():
    """
    追踪测试产生的所有 Redis 消息 ID
    清理时必须基于此字典精确删除，禁止使用通配符
    """
    return {
        "task_msg_ids": [],
        "result_msg_ids": [],
    }


@pytest.fixture(scope="session")
def tracked_problem_dirs():
    """
    追踪测试创建的所有 problem 目录
    清理时只删除这些具体目录，绝不删除父目录
    """
    return []


@pytest.fixture(scope="session", autouse=True)
async def redis_cleanup(tracked_msg_ids):
    """
    Session 结束时精确清理 Redis 消息
    只使用 XACK + XDEL，禁止删除流本身
    """
    yield

    from redis_client import redis_client

    for msg_id in tracked_msg_ids["task_msg_ids"]:
        try:
            await redis_client.xack("judge:tasks", "judge-workers", msg_id)
            await redis_client.xdel("judge:tasks", msg_id)
        except Exception as e:
            logging.warning(f"Failed to cleanup task msg {msg_id}: {e}")

    for msg_id in tracked_msg_ids["result_msg_ids"]:
        try:
            await redis_client.xdel("judge:results", msg_id)
        except Exception as e:
            logging.warning(f"Failed to cleanup result msg {msg_id}: {e}")


@pytest.fixture(scope="session", autouse=True)
def setup_test_case_dir():
    """
    Session 开始时创建测试用例目录
    注意：不在这里清理，由各 fixture 精确清理
    """
    TEST_CASE_DIR.mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture
def test_case_env(tracked_problem_dirs):
    """
    创建多测试点场景
    """
    problem_id = 1001
    problem_dir = TEST_CASE_DIR / str(problem_id)
    problem_dir.mkdir(exist_ok=True)
    tracked_problem_dirs.append(problem_dir)

    (problem_dir / "1.in").write_text("1 2\n3 4\n5 6\n")
    (problem_dir / "1.out").write_text("3\n7\n11\n")

    (problem_dir / "2.in").write_text("100 200\n")
    (problem_dir / "2.out").write_text("300\n")

    (problem_dir / "3.in").write_text("1000000000 1000000000\n")
    (problem_dir / "3.out").write_text("2000000000\n")

    info = {
        "problem_id": problem_id,
        "case_count": 3,
        "cases": [
            {"input": "1.in", "output": "1.out", "score": 33},
            {"input": "2.in", "output": "2.out", "score": 33},
            {"input": "3.in", "output": "3.out", "score": 34}
        ]
    }
    (problem_dir / "info.json").write_text(json.dumps(info))

    yield {
        "problem_id": problem_id,
        "test_case_dir": TEST_CASE_DIR,
        "case_count": 3,
    }

    if problem_dir.exists() and problem_dir.is_dir():
        shutil.rmtree(problem_dir)


@pytest.fixture
def test_case_single(tracked_problem_dirs):
    """
    单测试点场景
    """
    problem_id = 1002
    problem_dir = TEST_CASE_DIR / str(problem_id)
    problem_dir.mkdir(exist_ok=True)
    tracked_problem_dirs.append(problem_dir)

    (problem_dir / "1.in").write_text("1 2\n")
    (problem_dir / "1.out").write_text("3\n")

    info = {
        "problem_id": problem_id,
        "case_count": 1,
        "cases": [
            {"input": "1.in", "output": "1.out", "score": 100}
        ]
    }
    (problem_dir / "info.json").write_text(json.dumps(info))

    yield {
        "problem_id": problem_id,
        "test_case_dir": TEST_CASE_DIR,
        "case_count": 1,
    }

    if problem_dir.exists() and problem_dir.is_dir():
        shutil.rmtree(problem_dir)


@pytest.fixture
def test_case_mle(tracked_problem_dirs):
    """
    低内存限制测试用例
    """
    problem_id = 1003
    problem_dir = TEST_CASE_DIR / str(problem_id)
    problem_dir.mkdir(exist_ok=True)
    tracked_problem_dirs.append(problem_dir)

    (problem_dir / "1.in").write_text("1 2\n")
    (problem_dir / "1.out").write_text("3\n")

    info = {
        "problem_id": problem_id,
        "case_count": 1,
        "cases": [
            {"input": "1.in", "output": "1.out", "score": 100}
        ]
    }
    (problem_dir / "info.json").write_text(json.dumps(info))

    yield {
        "problem_id": problem_id,
        "test_case_dir": TEST_CASE_DIR,
        "case_count": 1,
    }

    if problem_dir.exists() and problem_dir.is_dir():
        shutil.rmtree(problem_dir)


@pytest.fixture
async def task_pusher(tracked_msg_ids):
    """
    推送判题任务到 Redis Stream
    返回消息 ID 并追踪
    """
    from redis_client import redis_client

    async def push(task: JudgeTask) -> str:
        msg_id = await redis_client.xadd(
            "judge:tasks",
            {"task": task.model_dump_json()}
        )
        tracked_msg_ids["task_msg_ids"].append(msg_id)
        return msg_id

    return push


@pytest.fixture
async def result_waiter(tracked_msg_ids):
    """
    从 judge:results 流等待指定 solution_id 的结果
    """
    from redis_client import redis_client

    async def wait(solution_id: int, timeout: int = 60) -> JudgeResult | None:
        start = asyncio.get_event_loop().time()
        last_id = "0"

        while asyncio.get_event_loop().time() - start < timeout:
            try:
                results = await redis_client.xread(
                    streams={"judge:results": last_id},
                    count=10,
                    block=1000
                )

                if results:
                    for stream_name, messages in results:
                        for msg_id, data in messages:
                            last_id = msg_id
                            tracked_msg_ids["result_msg_ids"].append(msg_id)
                            try:
                                result = JudgeResult.model_validate_json(data["result"])
                                if result.solution_id == solution_id:
                                    return result
                            except Exception:
                                continue
            except Exception as e:
                logging.warning(f"Error reading results: {e}")
                await asyncio.sleep(0.1)

        return None

    return wait


@pytest.fixture
async def submit_and_wait(task_pusher, result_waiter, tracked_msg_ids):
    """
    组合 fixture：推送任务并等待结果
    """
    async def _submit(
        solution_id: int,
        problem_id: int,
        language: Language,
        src: str,
        max_cpu_time: int = 1000,
        max_memory: int = 128,
        output: bool = False,
        is_spj: bool = False,
        ignore_space: bool = False,
        timeout: int = 60,
    ) -> JudgeResult | None:
        task = JudgeTask(
            solution_id=solution_id,
            language=language,
            src=src,
            max_cpu_time=max_cpu_time,
            max_memory=max_memory,
            problem_id=problem_id,
            output=output,
            is_spj=is_spj,
            ignore_space=ignore_space,
        )
        await task_pusher(task)
        return await result_waiter(solution_id, timeout)

    return _submit


@pytest.fixture
def cpp_ac_code() -> str:
    """
    正确的 A+B 代码（多组输入）
    """
    return """
#include <iostream>
using namespace std;
int main() {
    int a, b;
    while(cin >> a >> b) {
        cout << a + b << endl;
    }
    return 0;
}
"""


@pytest.fixture
def cpp_wa_code() -> str:
    """
    错误答案代码
    """
    return """
#include <iostream>
using namespace std;
int main() {
    int a, b;
    while(cin >> a >> b) {
        cout << a + b + 1 << endl;
    }
    return 0;
}
"""


@pytest.fixture
def cpp_pe_code() -> str:
    """
    格式错误代码（末尾多空格）
    """
    return """
#include <iostream>
using namespace std;
int main() {
    int a, b;
    while(cin >> a >> b) {
        cout << a + b << " " << endl;
    }
    return 0;
}
"""


@pytest.fixture
def cpp_re_code() -> str:
    """
    运行时错误代码（空指针解引用）
    """
    return """
#include <iostream>
using namespace std;
int main() {
    int *p = nullptr;
    *p = 0;
    return 0;
}
"""


@pytest.fixture
def cpp_tle_code() -> str:
    """
    超时代码（死循环）
    """
    return """
#include <iostream>
using namespace std;
int main() {
    while(true);
    return 0;
}
"""


@pytest.fixture
def cpp_mle_code() -> str:
    """
    内存超限代码（大数组分配）
    """
    return """
#include <iostream>
#include <vector>
using namespace std;
int main() {
    vector<int> v(10000000);
    return 0;
}
"""


@pytest.fixture
def cpp_ole_code() -> str:
    """
    输出超限代码（无限输出）
    """
    return """
#include <iostream>
using namespace std;
int main() {
    while(true) {
        cout << "Hello World!";
    }
    return 0;
}
"""


@pytest.fixture
def cpp_ce_code() -> str:
    """
    编译错误代码（缺少分号）
    """
    return """
#include <iostream>
using namespace std;
int main() {
    cout << "Hello" << endl
    return 0;
}
"""


@pytest.fixture
def cpp_division_by_zero_code() -> str:
    """
    除零错误代码
    """
    return """
#include <iostream>
using namespace std;
int main() {
    int a = 1 / 0;
    cout << a << endl;
    return 0;
}
"""


@pytest.fixture
def cpp_stack_overflow_code() -> str:
    """
    栈溢出代码（无限递归）
    """
    return """
#include <iostream>
using namespace std;
void f() { f(); }
int main() {
    f();
    return 0;
}
"""
