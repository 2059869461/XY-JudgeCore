from pydantic import BaseModel

class LanguageConfig(BaseModel):
    name: str
    src_name: str
    exe_name: str
    compile_cmd: str | None = None
    run_cmd: str
    compile_args: list[str] | None = None
    run_args: list[str] | None = None
    env: list[str] = ["LANG=en_US.UTF-8", "LANGUAGE=en_US:en", "LC_ALL=en_US.UTF-8"]
    
    # Compilation Resource Limits
    # GoJudge uses nanoseconds for time and bytes for memory
    compile_cpu_time: int = 20 * 1000 * 1000 * 1000  # 10s default
    compile_memory: int = 512 * 1024 * 1024          # 512MB default
    compile_output_limit: int = 10 * 1024 * 1024     # 10MB log limit

# 0=C, 1=C++, 2=Pascal, 3=Java, 4=Ruby, 5=Bash, 6=Python, 7=PHP, 8=Perl, 9=C#, 10=ObjC, 11=FreeBasic, 12=Scheme
# Supported: C(0), C++(1), Java(3), Python(6)

LANG_CONFIGS: dict[int, LanguageConfig] = {
    0: LanguageConfig(
        name="c",
        src_name="main.c",
        exe_name="main",
        compile_cmd="/usr/bin/gcc",
        compile_args=[
            "gcc", "main.c", "-o", "main",
            "-O2", "-w", "-fmax-errors=3", "-std=c99", "-lm"
        ],
        env=["PATH=/usr/bin:/bin"],
        run_cmd="main",
        run_args=["main"],
        compile_cpu_time=3 * 1000 * 1000 * 1000, # 3s for C
        compile_memory=256 * 1024 * 1024         # 256MB
    ),
    1: LanguageConfig(
        name="cpp",
        src_name="main.cpp",
        exe_name="main",
        compile_cmd="/usr/bin/g++",
        compile_args=[
            "g++", "main.cpp", "-o", "main",
            "-O2", "-w", "-fmax-errors=3", "-std=c++14", "-lm"
        ],
        env=["PATH=/usr/bin:/bin"],
        run_cmd="main",
        run_args=["main"],
        compile_cpu_time=10 * 1000 * 1000 * 1000, # 10s for C++ (templates can be slow)
        compile_memory=512 * 1024 * 1024,          # 512MB
    ),
    3: LanguageConfig(
        name="java",
        src_name="Main.java",
        exe_name="Main.jar",
        compile_cmd="/usr/bin/javac",
        compile_args=[
            "javac", "{src_path}", "-d", ".", "-encoding", "UTF8"
        ],
        run_cmd="/usr/bin/java",
        run_args=[
            "java", "-cp", ".", "-XX:MaxRAM={max_memory}k", 
            "-Djava.security.manager", "-Dfile.encoding=UTF-8", 
            "-Djava.awt.headless=true", "Main"
        ],
        compile_cpu_time=15 * 1000 * 1000 * 1000, # 15s for Java
        compile_memory=1024 * 1024 * 1024         # 1GB for JVM
    ),
    6: LanguageConfig(
        name="python",
        src_name="solution.py",
        exe_name="__pycache__/solution.cpython-312.pyc",
        compile_cmd="/usr/bin/python3",
        compile_args=[
            "python3", "-m", "py_compile", "{src_path}"
        ],
        run_cmd="/usr/bin/python3",
        run_args=["python3", "{src_path}"],
        env=["PYTHONIOENCODING=UTF-8", "LANG=en_US.UTF-8", "LANGUAGE=en_US:en", "LC_ALL=en_US.UTF-8"],
        compile_cpu_time=5 * 1000 * 1000 * 1000, # 5s for py_compile
        compile_memory=256 * 1024 * 1024
    ),
    666:LanguageConfig(
        name="checker",
        src_name="checker.cpp",
        exe_name="checker",
        run_cmd="./checker",
        run_args=["./checker","/dev/stdin","{ans}","2"],
        compile_cpu_time=3*1000*1000*1000,#实际为checker运行的时间限制而不是compile的时间
        compile_memory=512*1024*1024,
        env=["PATH=/usr/bin:/bin"],
    )
}

def get_language_config(lang_id: int) -> LanguageConfig:
    config = LANG_CONFIGS.get(lang_id)
    if not config:
        raise ValueError(f"Unsupported language ID: {lang_id}")
    return config
