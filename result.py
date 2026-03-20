
from enum import IntEnum
from pydantic import BaseModel

class JudgeStatus(IntEnum):
    PENDING = 0
    PENDING_REJUDGE = 1
    COMPILING = 2
    RUNNING = 3
    ACCEPTED = 4
    PRESENTATION_ERROR = 5
    WRONG_ANSWER = 6
    TIME_LIMIT_EXCEEDED = 7
    MEMORY_LIMIT_EXCEEDED = 8
    OUTPUT_LIMIT_EXCEEDED = 9
    RUNTIME_ERROR = 10
    COMPILE_ERROR = 11
    SYSTEM_ERROR = 12

class CaseResult(BaseModel):
    case_id: int
    case_result: JudgeStatus
    time_ms: int = 0
    memory_kb: int = 0

class JudgeResult(BaseModel):
    solution_id: int
    problem_id : int
    result: JudgeStatus
    result_list: list[CaseResult]|None = None
    time_ms: int = 0
    memory_kb: int = 0
    message:str|None =None
    pass_rate:int = 0