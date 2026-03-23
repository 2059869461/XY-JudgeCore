from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env" if not os.getenv("TESTING") else None, env_file_encoding="utf-8",extra="ignore")
    testing : bool = Field(default=False,validation_alias="TESTING")
    redis_url: str = Field(
        default="redis://localhost:6379",
        validation_alias="REDIS_URL",
    )
    judge_worker_name: str = Field(
        default="worker-1",
        validation_alias="JUDGE_WORKER_NAME",
    )
    judge_worker_concurrency: int = Field(
        default=10,
        validation_alias="JUDGE_WORKER_CONCURRENCY",
    )
    judge_worker_block_ms: int = Field(
        default=10000,
        validation_alias="JUDGE_WORKER_BLOCK_MS",
    )
    judge_worker_pending_idle_ms: int = Field(
        default=60000,
        validation_alias="JUDGE_WORKER_PENDING_IDLE_MS",
    )
    judge_worker_max_server_cpu: float = Field(
        default=85,
        validation_alias="JUDGE_WORKER_MAX_SERVER_CPU",
    )
    judge_worker_max_server_memory: float = Field(
        default=85,
        validation_alias="JUDGE_WORKER_MAX_SERVER_MEMORY",
    )

    test_case_dir_ : str = Field(
        default="/home/nianhe/oj_project/test_case",
        validation_alias="TEST_CASE_DIR"
    )
    tmp_test_case_dir_ : str = Field(
        default="/tmp/judgeworker_test_cases",
        validation_alias="TMP_TEST_CASE_DIR"
    )
    gojudge_url : str = Field(
        default="http://localhost:5050",
        validation_alias="GOJUDGE_URL"
    )
    checker_cache_size : int = Field(
        default=3000,
        validation_alias="CHECKER_CACHE_SIZE"
    )
    @property
    def test_case_dir(self)->str:
        return self.tmp_test_case_dir_ if self.testing else self.test_case_dir_

settings = Settings()