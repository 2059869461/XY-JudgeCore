"""
判题状态边界测试 - 验证各种判题状态 (AC, WA, PE, RE, TLE, MLE, OLE, CE)
"""
import pytest
from result import JudgeStatus
from languages import Language


SOLUTION_ID_BASE = 10000


@pytest.mark.asyncio
async def test_ac_status(submit_and_wait, test_case_env, cpp_ac_code):
    """测试 Accepted (AC) - 正确答案"""
    result = await submit_and_wait(
        solution_id=SOLUTION_ID_BASE + 1,
        problem_id=test_case_env["problem_id"],
        language=Language.CPP17,
        src=cpp_ac_code,
        max_cpu_time=1000,
        max_memory=128,
    )

    assert result is not None, "未收到判题结果"
    assert result.result == JudgeStatus.ACCEPTED, f"期望 AC，实际: {result.result}"
    assert result.pass_rate == 10000, f"期望 pass_rate=10000，实际: {result.pass_rate}"
    assert result.time_ms >= 0, f"无效的执行时间: {result.time_ms}"
    assert result.memory_kb >= 0, f"无效的内存使用: {result.memory_kb}"


@pytest.mark.asyncio
async def test_wa_status(submit_and_wait, test_case_env, cpp_wa_code):
    """测试 Wrong Answer (WA) - 错误答案"""
    result = await submit_and_wait(
        solution_id=SOLUTION_ID_BASE + 2,
        problem_id=test_case_env["problem_id"],
        language=Language.CPP17,
        src=cpp_wa_code,
        max_cpu_time=1000,
        max_memory=128,
    )

    assert result is not None, "未收到判题结果"
    assert result.result == JudgeStatus.WRONG_ANSWER, f"期望 WA，实际: {result.result}"
    assert result.pass_rate == 0, f"期望 pass_rate=0，实际: {result.pass_rate}"


@pytest.mark.asyncio
async def test_pe_status(submit_and_wait, test_case_env, cpp_pe_code):
    """测试 Presentation Error (PE) - 格式错误"""
    result = await submit_and_wait(
        solution_id=SOLUTION_ID_BASE + 3,
        problem_id=test_case_env["problem_id"],
        language=Language.CPP17,
        src=cpp_pe_code,
        max_cpu_time=1000,
        max_memory=128,
    )

    assert result is not None, "未收到判题结果"
    assert result.result == JudgeStatus.PRESENTATION_ERROR, f"期望 PE，实际: {result.result}"


@pytest.mark.asyncio
async def test_re_status(submit_and_wait, test_case_single, cpp_re_code):
    """测试 Runtime Error (RE) - 运行时错误（空指针解引用）"""
    result = await submit_and_wait(
        solution_id=SOLUTION_ID_BASE + 4,
        problem_id=test_case_single["problem_id"],
        language=Language.CPP17,
        src=cpp_re_code,
        max_cpu_time=1000,
        max_memory=128,
    )

    assert result is not None, "未收到判题结果"
    assert result.result == JudgeStatus.RUNTIME_ERROR, f"期望 RE，实际: {result.result}"


@pytest.mark.asyncio
async def test_tle_status(submit_and_wait, test_case_single, cpp_tle_code):
    """测试 Time Limit Exceeded (TLE) - 超时"""
    result = await submit_and_wait(
        solution_id=SOLUTION_ID_BASE + 5,
        problem_id=test_case_single["problem_id"],
        language=Language.CPP17,
        src=cpp_tle_code,
        max_cpu_time=1000,
        max_memory=128,
        timeout=30,
    )

    assert result is not None, "未收到判题结果"
    assert result.result == JudgeStatus.TIME_LIMIT_EXCEEDED, f"期望 TLE，实际: {result.result}"
    assert result.time_ms >= 1000, f"TLE 时间应 >= 1000ms，实际: {result.time_ms}"


@pytest.mark.asyncio
async def test_mle_status(submit_and_wait, test_case_mle, cpp_mle_code):
    """测试 Memory Limit Exceeded (MLE) - 内存超限"""
    result = await submit_and_wait(
        solution_id=SOLUTION_ID_BASE + 6,
        problem_id=test_case_mle["problem_id"],
        language=Language.CPP17,
        src=cpp_mle_code,
        max_cpu_time=1000,
        max_memory=32,
    )

    assert result is not None, "未收到判题结果"
    assert result.result == JudgeStatus.MEMORY_LIMIT_EXCEEDED, f"期望 MLE，实际: {result.result}"
    memory_limit_kb = 32 * 1024
    assert result.memory_kb > memory_limit_kb, f"MLE 内存应 > {memory_limit_kb}KB，实际: {result.memory_kb}"


@pytest.mark.asyncio
async def test_ole_status(submit_and_wait, test_case_single, cpp_ole_code):
    """测试 Output Limit Exceeded (OLE) - 输出超限"""
    result = await submit_and_wait(
        solution_id=SOLUTION_ID_BASE + 7,
        problem_id=test_case_single["problem_id"],
        language=Language.CPP17,
        src=cpp_ole_code,
        max_cpu_time=1000,
        max_memory=128,
        timeout=30,
    )

    assert result is not None, "未收到判题结果"
    assert result.result == JudgeStatus.OUTPUT_LIMIT_EXCEEDED, f"期望 OLE，实际: {result.result}"


@pytest.mark.asyncio
async def test_ce_status(submit_and_wait, test_case_single, cpp_ce_code):
    """测试 Compile Error (CE) - 编译错误"""
    result = await submit_and_wait(
        solution_id=SOLUTION_ID_BASE + 8,
        problem_id=test_case_single["problem_id"],
        language=Language.CPP17,
        src=cpp_ce_code,
        max_cpu_time=1000,
        max_memory=128,
    )

    assert result is not None, "未收到判题结果"
    assert result.result == JudgeStatus.COMPILE_ERROR, f"期望 CE，实际: {result.result}"
    assert result.message is not None, "CE 应该有错误信息"


@pytest.mark.asyncio
async def test_division_by_zero(submit_and_wait, test_case_single, cpp_division_by_zero_code):
    """测试除零错误 - 应该返回 RE"""
    result = await submit_and_wait(
        solution_id=SOLUTION_ID_BASE + 9,
        problem_id=test_case_single["problem_id"],
        language=Language.CPP17,
        src=cpp_division_by_zero_code,
        max_cpu_time=1000,
        max_memory=128,
    )

    assert result is not None, "未收到判题结果"
    assert result.result == JudgeStatus.RUNTIME_ERROR, f"期望 RE，实际: {result.result}"


@pytest.mark.asyncio
async def test_stack_overflow(submit_and_wait, test_case_single, cpp_stack_overflow_code):
    """测试栈溢出 - 应该返回 RE"""
    result = await submit_and_wait(
        solution_id=SOLUTION_ID_BASE + 10,
        problem_id=test_case_single["problem_id"],
        language=Language.CPP17,
        src=cpp_stack_overflow_code,
        max_cpu_time=1000,
        max_memory=128,
        timeout=30,
    )

    assert result is not None, "未收到判题结果"
    assert result.result in [JudgeStatus.RUNTIME_ERROR, JudgeStatus.TIME_LIMIT_EXCEEDED], \
        f"期望 RE 或 TLE，实际: {result.result}"


@pytest.mark.asyncio
async def test_ignore_space_mode(submit_and_wait, test_case_single, cpp_pe_code):
    """测试 ignore_space=True 时 PE 代码应该变成 AC"""
    result = await submit_and_wait(
        solution_id=SOLUTION_ID_BASE + 11,
        problem_id=test_case_single["problem_id"],
        language=Language.CPP17,
        src=cpp_pe_code,
        max_cpu_time=1000,
        max_memory=128,
        ignore_space=True,
    )

    assert result is not None, "未收到判题结果"
    assert result.result == JudgeStatus.ACCEPTED, f"ignore_space=True 时期望 AC，实际: {result.result}"


@pytest.mark.asyncio
async def test_large_number(submit_and_wait, test_case_env, cpp_ac_code):
    """测试大数运算 - 1000000000 + 1000000000 = 2000000000"""
    result = await submit_and_wait(
        solution_id=SOLUTION_ID_BASE + 12,
        problem_id=test_case_env["problem_id"],
        language=Language.CPP17,
        src=cpp_ac_code,
        max_cpu_time=1000,
        max_memory=128,
    )

    assert result is not None, "未收到判题结果"
    assert result.result == JudgeStatus.ACCEPTED, f"期望 AC，实际: {result.result}"
    assert result.result_list is not None, "应该有测试点详情"
    assert len(result.result_list) == test_case_env["case_count"], \
        f"测试点数量不匹配，期望: {test_case_env['case_count']}，实际: {len(result.result_list)}"


@pytest.mark.asyncio
async def test_result_list_correctness(submit_and_wait, test_case_env, cpp_ac_code):
    """测试 result_list 中每个测试点的结果正确性"""
    result = await submit_and_wait(
        solution_id=SOLUTION_ID_BASE + 13,
        problem_id=test_case_env["problem_id"],
        language=Language.CPP17,
        src=cpp_ac_code,
        max_cpu_time=1000,
        max_memory=128,
    )

    assert result is not None, "未收到判题结果"
    assert result.result_list is not None, "应该有测试点详情"

    for i, case_result in enumerate(result.result_list):
        assert case_result.case_id == i + 1, f"测试点 ID 不正确: {case_result.case_id}"
        assert case_result.case_result == JudgeStatus.ACCEPTED, \
            f"测试点 {case_result.case_id} 应该是 AC，实际: {case_result.case_result}"
        assert case_result.time_ms >= 0, f"测试点 {case_result.case_id} 时间无效"
        assert case_result.memory_kb >= 0, f"测试点 {case_result.case_id} 内存无效"


@pytest.mark.asyncio
async def test_different_cpp_standards(submit_and_wait, tracked_problem_dirs):
    """测试不同 C++ 标准都能正确编译运行"""
    import json
    import shutil
    from pathlib import Path
    from config import settings

    test_case_dir = Path(settings.test_case_dir)
    problem_id = 2001
    problem_dir = test_case_dir / str(problem_id)
    problem_dir.mkdir(parents=True, exist_ok=True)
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

    cpp_code = """
#include <iostream>
int main() {
    int a, b;
    std::cin >> a >> b;
    std::cout << a + b << std::endl;
    return 0;
}
"""

    standards = [Language.CPP11, Language.CPP14, Language.CPP17, Language.CPP20]

    for i, lang in enumerate(standards):
        result = await submit_and_wait(
            solution_id=SOLUTION_ID_BASE + 100 + i,
            problem_id=problem_id,
            language=lang,
            src=cpp_code,
            max_cpu_time=1000,
            max_memory=128,
        )

        assert result is not None, f"{lang.name} 未收到判题结果"
        assert result.result == JudgeStatus.ACCEPTED, f"{lang.name} 期望 AC，实际: {result.result}"

    import shutil
    if problem_dir.exists() and problem_dir.is_dir():
        shutil.rmtree(problem_dir)
