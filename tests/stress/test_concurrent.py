"""
并发负载测试 - 验证系统在高并发下的稳定性
"""
import pytest
import asyncio
from result import JudgeStatus
from languages import Language
from task import JudgeTask


CONCURRENT_SOLUTION_ID_BASE = 30000


@pytest.mark.asyncio
async def test_concurrent_submissions(submit_and_wait, test_case_env, cpp_ac_code):
    """
    测试 10 个并发提交
    验证所有任务都能正确处理并返回正确结果
    """
    concurrency = 10
    tasks = []

    for i in range(concurrency):
        task = submit_and_wait(
            solution_id=CONCURRENT_SOLUTION_ID_BASE + i,
            problem_id=test_case_env["problem_id"],
            language=Language.CPP17,
            src=cpp_ac_code,
            max_cpu_time=1000,
            max_memory=128,
            timeout=120,
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    for i, result in enumerate(results):
        assert result is not None, f"任务 {i} 未收到结果"
        assert result.result == JudgeStatus.ACCEPTED, \
            f"任务 {i} 期望 AC，实际: {result.result}"
        assert result.solution_id == CONCURRENT_SOLUTION_ID_BASE + i, \
            f"任务 {i} solution_id 不匹配"


@pytest.mark.asyncio
async def test_concurrent_mixed_status(submit_and_wait, test_case_env, cpp_ac_code, cpp_wa_code, cpp_ce_code):
    """
    测试并发提交不同状态的代码
    验证每个任务都能返回正确的状态
    """
    test_cases = [
        (CONCURRENT_SOLUTION_ID_BASE + 100, cpp_ac_code, JudgeStatus.ACCEPTED),
        (CONCURRENT_SOLUTION_ID_BASE + 101, cpp_wa_code, JudgeStatus.WRONG_ANSWER),
        (CONCURRENT_SOLUTION_ID_BASE + 102, cpp_ac_code, JudgeStatus.ACCEPTED),
        (CONCURRENT_SOLUTION_ID_BASE + 103, cpp_ce_code, JudgeStatus.COMPILE_ERROR),
        (CONCURRENT_SOLUTION_ID_BASE + 104, cpp_ac_code, JudgeStatus.ACCEPTED),
    ]

    tasks = []
    for solution_id, code, expected_status in test_cases:
        task = submit_and_wait(
            solution_id=solution_id,
            problem_id=test_case_env["problem_id"],
            language=Language.CPP17,
            src=code,
            max_cpu_time=1000,
            max_memory=128,
            timeout=120,
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    for i, (result, (_, _, expected_status)) in enumerate(zip(results, test_cases)):
        assert result is not None, f"任务 {i} 未收到结果"
        assert result.result == expected_status, \
            f"任务 {i} 期望 {expected_status}，实际: {result.result}"


@pytest.mark.asyncio
async def test_high_concurrency(submit_and_wait, test_case_env, cpp_ac_code):
    """
    测试 20 个高并发提交
    验证系统在高负载下的稳定性
    """
    concurrency = 20
    tasks = []

    for i in range(concurrency):
        task = submit_and_wait(
            solution_id=CONCURRENT_SOLUTION_ID_BASE + 200 + i,
            problem_id=test_case_env["problem_id"],
            language=Language.CPP17,
            src=cpp_ac_code,
            max_cpu_time=1000,
            max_memory=128,
            timeout=180,
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    success_count = 0
    for i, result in enumerate(results):
        if result is not None and result.result == JudgeStatus.ACCEPTED:
            success_count += 1

    assert success_count == concurrency, \
        f"期望 {concurrency} 个成功，实际: {success_count}"


@pytest.mark.asyncio
async def test_sequential_vs_concurrent(submit_and_wait, test_case_env, cpp_ac_code):
    """
    测试顺序执行和并发执行的结果一致性
    """
    num_tasks = 5

    sequential_results = []
    for i in range(num_tasks):
        result = await submit_and_wait(
            solution_id=CONCURRENT_SOLUTION_ID_BASE + 300 + i,
            problem_id=test_case_env["problem_id"],
            language=Language.CPP17,
            src=cpp_ac_code,
            max_cpu_time=1000,
            max_memory=128,
        )
        sequential_results.append(result)

    concurrent_tasks = []
    for i in range(num_tasks):
        task = submit_and_wait(
            solution_id=CONCURRENT_SOLUTION_ID_BASE + 400 + i,
            problem_id=test_case_env["problem_id"],
            language=Language.CPP17,
            src=cpp_ac_code,
            max_cpu_time=1000,
            max_memory=128,
            timeout=120,
        )
        concurrent_tasks.append(task)

    concurrent_results = await asyncio.gather(*concurrent_tasks)

    for i, (seq_result, conc_result) in enumerate(zip(sequential_results, concurrent_results)):
        assert seq_result is not None, f"顺序任务 {i} 未收到结果"
        assert conc_result is not None, f"并发任务 {i} 未收到结果"
        assert seq_result.result == conc_result.result, \
            f"任务 {i} 结果不一致: 顺序={seq_result.result}, 并发={conc_result.result}"


@pytest.mark.asyncio
async def test_burst_submissions(task_pusher, result_waiter, test_case_env, cpp_ac_code, tracked_msg_ids):
    """
    测试突发大量提交
    短时间内推送大量任务，验证系统处理能力
    """
    burst_count = 15
    solution_ids = [CONCURRENT_SOLUTION_ID_BASE + 500 + i for i in range(burst_count)]

    for solution_id in solution_ids:
        task = JudgeTask(
            solution_id=solution_id,
            language=Language.CPP17,
            src=cpp_ac_code,
            max_cpu_time=1000,
            max_memory=128,
            problem_id=test_case_env["problem_id"],
            output=False,
            is_spj=False,
            ignore_space=False,
        )
        await task_pusher(task)

    results = []
    for solution_id in solution_ids:
        result = await result_waiter(solution_id, timeout=180)
        results.append(result)

    success_count = sum(1 for r in results if r is not None and r.result == JudgeStatus.ACCEPTED)
    assert success_count == burst_count, f"期望 {burst_count} 个成功，实际: {success_count}"


@pytest.mark.asyncio
async def test_long_running_concurrent(submit_and_wait, test_case_env):
    """
    测试长时间运行任务的并发处理
    """
    long_running_code = """
#include <iostream>
using namespace std;
int main() {
    int a, b;
    cin >> a >> b;
    for(int i = 0; i < 1000000; i++) {
        a = (a + 1) % 1000000007;
    }
    cout << a + b << endl;
    return 0;
}
"""

    concurrency = 5
    tasks = []

    for i in range(concurrency):
        task = submit_and_wait(
            solution_id=CONCURRENT_SOLUTION_ID_BASE + 600 + i,
            problem_id=test_case_env["problem_id"],
            language=Language.CPP17,
            src=long_running_code,
            max_cpu_time=2000,
            max_memory=128,
            timeout=120,
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    for i, result in enumerate(results):
        assert result is not None, f"任务 {i} 未收到结果"
        assert result.result in [JudgeStatus.ACCEPTED, JudgeStatus.WRONG_ANSWER], \
            f"任务 {i} 意外状态: {result.result}"
