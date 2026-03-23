"""
幂等性测试 - 验证同一任务多次执行结果一致性
"""
import pytest
import asyncio
from result import JudgeStatus
from languages import Language


IDEMPOTENCY_SOLUTION_ID = 20000


@pytest.mark.asyncio
async def test_same_solution_idempotency(submit_and_wait, test_case_env, cpp_ac_code):
    """
    测试同一 solution_id 多次执行，结果应一致
    验证：判题状态、通过率、时间误差在合理范围
    """
    results = []

    for i in range(3):
        result = await submit_and_wait(
            solution_id=IDEMPOTENCY_SOLUTION_ID,
            problem_id=test_case_env["problem_id"],
            language=Language.CPP17,
            src=cpp_ac_code,
            max_cpu_time=1000,
            max_memory=128,
        )
        assert result is not None, f"第 {i+1} 次执行未收到结果"
        results.append(result)
        await asyncio.sleep(0.5)

    first_result = results[0]

    for i, result in enumerate(results):
        assert result.result == first_result.result, \
            f"第 {i+1} 次执行结果状态不一致: {result.result} vs {first_result.result}"

    for i, result in enumerate(results):
        assert result.pass_rate == first_result.pass_rate, \
            f"第 {i+1} 次执行通过率不一致: {result.pass_rate} vs {first_result.pass_rate}"

    times = [r.time_ms for r in results]
    max_time = max(times)
    min_time = min(times)
    if min_time > 0:
        ratio = max_time / min_time
        assert ratio < 2.0, f"执行时间差异过大: {times}，比值: {ratio:.2f}"

    memories = [r.memory_kb for r in results]
    max_mem = max(memories)
    min_mem = min(memories)
    if min_mem > 0:
        mem_ratio = max_mem / min_mem
        assert mem_ratio < 2.0, f"内存使用差异过大: {memories}，比值: {mem_ratio:.2f}"


@pytest.mark.asyncio
async def test_wa_idempotency(submit_and_wait, test_case_env, cpp_wa_code):
    """
    测试 WA 状态的幂等性
    """
    results = []

    for i in range(3):
        result = await submit_and_wait(
            solution_id=IDEMPOTENCY_SOLUTION_ID + 1,
            problem_id=test_case_env["problem_id"],
            language=Language.CPP17,
            src=cpp_wa_code,
            max_cpu_time=1000,
            max_memory=128,
        )
        assert result is not None, f"第 {i+1} 次执行未收到结果"
        results.append(result)
        await asyncio.sleep(0.5)

    for i, result in enumerate(results):
        assert result.result == JudgeStatus.WRONG_ANSWER, \
            f"第 {i+1} 次执行结果状态不一致: {result.result}"
        assert result.pass_rate == 0, f"第 {i+1} 次执行通过率应为 0"


@pytest.mark.asyncio
async def test_ce_idempotency(submit_and_wait, test_case_single, cpp_ce_code):
    """
    测试 CE 状态的幂等性
    编译错误应该每次都一致
    """
    results = []

    for i in range(3):
        result = await submit_and_wait(
            solution_id=IDEMPOTENCY_SOLUTION_ID + 2,
            problem_id=test_case_single["problem_id"],
            language=Language.CPP17,
            src=cpp_ce_code,
            max_cpu_time=1000,
            max_memory=128,
        )
        assert result is not None, f"第 {i+1} 次执行未收到结果"
        results.append(result)
        await asyncio.sleep(0.5)

    for i, result in enumerate(results):
        assert result.result == JudgeStatus.COMPILE_ERROR, \
            f"第 {i+1} 次执行结果状态不一致: {result.result}"
        assert result.message is not None, f"第 {i+1} 次执行缺少编译错误信息"


@pytest.mark.asyncio
async def test_different_solution_ids_independence(submit_and_wait, test_case_env, cpp_ac_code, cpp_wa_code):
    """
    测试不同 solution_id 的任务互不影响
    """
    ac_result = await submit_and_wait(
        solution_id=IDEMPOTENCY_SOLUTION_ID + 100,
        problem_id=test_case_env["problem_id"],
        language=Language.CPP17,
        src=cpp_ac_code,
        max_cpu_time=1000,
        max_memory=128,
    )

    wa_result = await submit_and_wait(
        solution_id=IDEMPOTENCY_SOLUTION_ID + 101,
        problem_id=test_case_env["problem_id"],
        language=Language.CPP17,
        src=cpp_wa_code,
        max_cpu_time=1000,
        max_memory=128,
    )

    assert ac_result is not None, "AC 任务未收到结果"
    assert wa_result is not None, "WA 任务未收到结果"
    assert ac_result.solution_id == IDEMPOTENCY_SOLUTION_ID + 100
    assert wa_result.solution_id == IDEMPOTENCY_SOLUTION_ID + 101
    assert ac_result.result == JudgeStatus.ACCEPTED
    assert wa_result.result == JudgeStatus.WRONG_ANSWER


@pytest.mark.asyncio
async def test_resource_limit_consistency(submit_and_wait, test_case_env, cpp_ac_code):
    """
    测试资源限制的一致性
    同样的代码在相同限制下，资源使用应该接近
    """
    results = []

    for i in range(5):
        result = await submit_and_wait(
            solution_id=IDEMPOTENCY_SOLUTION_ID + 200 + i,
            problem_id=test_case_env["problem_id"],
            language=Language.CPP17,
            src=cpp_ac_code,
            max_cpu_time=1000,
            max_memory=128,
        )
        assert result is not None, f"第 {i+1} 次执行未收到结果"
        results.append(result)
        await asyncio.sleep(0.3)

    times = [r.time_ms for r in results]
    memories = [r.memory_kb for r in results]

    avg_time = sum(times) / len(times)
    avg_memory = sum(memories) / len(memories)

    for i, (t, m) in enumerate(zip(times, memories)):
        if avg_time > 0:
            time_deviation = abs(t - avg_time) / avg_time
            assert time_deviation < 0.5, \
                f"第 {i+1} 次执行时间偏差过大: {t}ms vs 平均 {avg_time:.2f}ms"

        if avg_memory > 0:
            mem_deviation = abs(m - avg_memory) / avg_memory
            assert mem_deviation < 0.5, \
                f"第 {i+1} 次执行内存偏差过大: {m}KB vs 平均 {avg_memory:.2f}KB"


@pytest.mark.asyncio
async def test_result_list_idempotency(submit_and_wait, test_case_env, cpp_ac_code):
    """
    测试 result_list 的幂等性
    每次执行应该返回相同数量和顺序的测试点结果
    """
    results = []

    for i in range(3):
        result = await submit_and_wait(
            solution_id=IDEMPOTENCY_SOLUTION_ID + 300,
            problem_id=test_case_env["problem_id"],
            language=Language.CPP17,
            src=cpp_ac_code,
            max_cpu_time=1000,
            max_memory=128,
        )
        assert result is not None, f"第 {i+1} 次执行未收到结果"
        results.append(result)
        await asyncio.sleep(0.5)

    first_list = results[0].result_list
    assert first_list is not None, "result_list 不应为空"
    expected_count = len(first_list)

    for i, result in enumerate(results):
        assert result.result_list is not None, f"第 {i+1} 次执行 result_list 为空"
        assert len(result.result_list) == expected_count, \
            f"第 {i+1} 次执行测试点数量不一致: {len(result.result_list)} vs {expected_count}"

        for j, case_result in enumerate(result.result_list):
            assert case_result.case_id == first_list[j].case_id, \
                f"第 {i+1} 次执行测试点 {j} ID 不一致"
            assert case_result.case_result == first_list[j].case_result, \
                f"第 {i+1} 次执行测试点 {j} 结果不一致"
