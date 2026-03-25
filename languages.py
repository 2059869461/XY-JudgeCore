from pydantic import BaseModel
from enum import IntEnum

class Language(IntEnum):
    C99 = 0
    C11 = 1
    C17 = 2
    C23 = 3
    CPP11 = 4
    CPP14 = 5
    CPP17 = 6
    CPP20 = 7
    CPP23 = 8
    JAVA = 9
    GO = 10
    RUST = 11
    PYTHON3 = 12
    NODEJS = 13
    KOTLIN = 14
    CSHARP = 15
    PASCAL = 16
    TYPESCRIPT = 17
    CHECKER = 666

class LanguageConfig(BaseModel):
    name: str
    src_name: str
    exe_name: str
    compile_args: list[str] 
    run_args: list[str]
    env: list[str]
    
    compile_cpu_time: int
    compile_memory: int

LANG_CONFIGS: dict[int, LanguageConfig] = {
    Language.C99: LanguageConfig(
        name="c99",
        src_name="main.c",
        exe_name="main",
        compile_args=[
            "gcc", "main.c", "-o", "main",
            "-O2", "-w", "-fmax-errors=3", "-std=c99", "-lm"
        ],
        env=["PATH=/usr/bin:/bin"],
        run_args=["./main"],
        compile_cpu_time=3 * 1000 * 1000 * 1000,
        compile_memory=256 * 1024 * 1024
    ),
    Language.C11: LanguageConfig(
        name="c11",
        src_name="main.c",
        exe_name="main",
        compile_args=[
            "gcc", "main.c", "-o", "main",
            "-O2", "-w", "-fmax-errors=3", "-std=c11", "-lm"
        ],
        env=["PATH=/usr/bin:/bin"],
        run_args=["./main"],
        compile_cpu_time=3 * 1000 * 1000 * 1000,
        compile_memory=256 * 1024 * 1024
    ),
    Language.C17: LanguageConfig(
        name="c17",
        src_name="main.c",
        exe_name="main",
        compile_args=[
            "gcc", "main.c", "-o", "main",
            "-O2", "-w", "-fmax-errors=3", "-std=c17", "-lm"
        ],
        env=["PATH=/usr/bin:/bin"],
        run_args=["./main"],
        compile_cpu_time=3 * 1000 * 1000 * 1000,
        compile_memory=256 * 1024 * 1024
    ),
    Language.C23: LanguageConfig(
        name="c23",
        src_name="main.c",
        exe_name="main",
        compile_args=[
            "gcc", "main.c", "-o", "main",
            "-O2", "-w", "-fmax-errors=3", "-std=c23", "-lm"
        ],
        env=["PATH=/usr/bin:/bin"],
        run_args=["./main"],
        compile_cpu_time=3 * 1000 * 1000 * 1000,
        compile_memory=256 * 1024 * 1024
    ),
    Language.CPP11: LanguageConfig(
        name="cpp11",
        src_name="main.cpp",
        exe_name="main",
        compile_args=[
            "g++", "main.cpp", "-o", "main",
            "-O2", "-w", "-fmax-errors=3", "-std=c++11", "-lm"
        ],
        env=["PATH=/usr/bin:/bin"],
        run_args=["./main"],
        compile_cpu_time=10 * 1000 * 1000 * 1000,
        compile_memory=512 * 1024 * 1024,
    ),
    Language.CPP14: LanguageConfig(
        name="cpp14",
        src_name="main.cpp",
        exe_name="main",
        compile_args=[
            "g++", "main.cpp", "-o", "main",
            "-O2", "-w", "-fmax-errors=3", "-std=c++14", "-lm"
        ],
        env=["PATH=/usr/bin:/bin"],
        run_args=["./main"],
        compile_cpu_time=10 * 1000 * 1000 * 1000,
        compile_memory=512 * 1024 * 1024,
    ),
    Language.CPP17: LanguageConfig(
        name="cpp17",
        src_name="main.cpp",
        exe_name="main",
        compile_args=[
            "g++", "main.cpp", "-o", "main",
            "-O2", "-w", "-fmax-errors=3", "-std=c++17", "-lm"
        ],
        env=["PATH=/usr/bin:/bin"],
        run_args=["./main"],
        compile_cpu_time=10 * 1000 * 1000 * 1000,
        compile_memory=512 * 1024 * 1024,
    ),
    Language.CPP20: LanguageConfig(
        name="cpp20",
        src_name="main.cpp",
        exe_name="main",
        compile_args=[
            "g++", "main.cpp", "-o", "main",
            "-O2", "-w", "-fmax-errors=3", "-std=c++20", "-lm"
        ],
        env=["PATH=/usr/bin:/bin"],
        run_args=["./main"],
        compile_cpu_time=10 * 1000 * 1000 * 1000,
        compile_memory=512 * 1024 * 1024,
    ),
    Language.CPP23: LanguageConfig(
        name="cpp23",
        src_name="main.cpp",
        exe_name="main",
        compile_args=[
            "g++", "main.cpp", "-o", "main",
            "-O2", "-w", "-fmax-errors=3", "-std=c++23", "-lm"
        ],
        env=["PATH=/usr/bin:/bin"],
        run_args=["./main"],
        compile_cpu_time=10 * 1000 * 1000 * 1000,
        compile_memory=512 * 1024 * 1024,
    ),
    Language.JAVA: LanguageConfig(
        name="java",
        src_name="Main.java",
        exe_name="Main",
        compile_args=[
            "javac", "Main.java", "-d", ".", "-encoding", "UTF8"
        ],
        run_args=[
            "java", "-cp", ".", 
            "-Djava.security.manager", "-Dfile.encoding=UTF-8", 
            "-Djava.awt.headless=true", "Main"
        ],
        env=["PATH=/usr/bin:/bin", "JAVA_HOME=/usr/lib/jvm/default-java"],
        compile_cpu_time=15 * 1000 * 1000 * 1000,
        compile_memory=1024 * 1024 * 1024
    ),
    Language.GO: LanguageConfig(
        name="go",
        src_name="main.go",
        exe_name="main",
        compile_args=[
            "go", "build", "-o", "main", "main.go"
        ],
        env=["PATH=/usr/local/go/bin:/usr/bin:/bin", "GOPATH=/tmp/go", "GOCACHE=/tmp/go-cache"],
        run_args=["./main"],
        compile_cpu_time=15 * 1000 * 1000 * 1000,
        compile_memory=512 * 1024 * 1024
    ),
    Language.RUST: LanguageConfig(
        name="rust",
        src_name="main.rs",
        exe_name="main",
        compile_args=[
            "rustc", "-O", "-o", "main", "main.rs"
        ],
        env=["PATH=/usr/local/cargo/bin:/usr/bin:/bin"],
        run_args=["./main"],
        compile_cpu_time=20 * 1000 * 1000 * 1000,
        compile_memory=1024 * 1024 * 1024
    ),
    Language.PYTHON3: LanguageConfig(
        name="python3",
        src_name="solution.py",
        exe_name="solution.py",
        compile_args=["python3", "-m", "py_compile", "solution.py"],
        run_args=["python3", "solution.py"],
        env=["PYTHONIOENCODING=UTF-8", "PATH=/usr/bin:/bin"],
        compile_cpu_time=5 * 1000 * 1000 * 1000,
        compile_memory=256 * 1024 * 1024
    ),
    Language.NODEJS: LanguageConfig(
        name="nodejs",
        src_name="solution.js",
        exe_name="solution.js",
        compile_args=["node", "--check", "solution.js"],
        run_args=["node", "solution.js"],
        env=["PATH=/usr/bin:/bin", "NODE_OPTIONS=--max-old-space-size=256"],
        compile_cpu_time=5 * 1000 * 1000 * 1000,
        compile_memory=256 * 1024 * 1024
    ),
    Language.KOTLIN: LanguageConfig(
        name="kotlin",
        src_name="Main.kt",
        exe_name="Main.jar",
        compile_args=["kotlinc", "Main.kt", "-include-runtime", "-d", "Main.jar"],
        run_args=["java", "-jar", "Main.jar"],
        env=["PATH=/usr/bin:/bin", "JAVA_HOME=/usr/lib/jvm/default-java"],
        compile_cpu_time=20 * 1000 * 1000 * 1000,
        compile_memory=1024 * 1024 * 1024
    ),
    Language.CSHARP: LanguageConfig(
        name="csharp",
        src_name="Main.cs",
        exe_name="Main.exe",
        compile_args=["mcs", "-optimize+", "-out:Main.exe", "Main.cs"],
        run_args=["mono", "Main.exe"],
        env=["PATH=/usr/bin:/bin"],
        compile_cpu_time=15 * 1000 * 1000 * 1000,
        compile_memory=512 * 1024 * 1024
    ),
    Language.PASCAL: LanguageConfig(
        name="pascal",
        src_name="main.pas",
        exe_name="main",
        compile_args=["fpc", "-O2", "-o main", "main.pas"],
        run_args=["./main"],
        env=["PATH=/usr/bin:/bin"],
        compile_cpu_time=10 * 1000 * 1000 * 1000,
        compile_memory=256 * 1024 * 1024
    ),
    Language.TYPESCRIPT: LanguageConfig(
        name="typescript",
        src_name="solution.ts",
        exe_name="solution.js",
        compile_args=["tsc", "--outDir", ".", "solution.ts"],
        run_args=["node", "solution.js"],
        env=["PATH=/usr/bin:/bin", "NODE_OPTIONS=--max-old-space-size=256"],
        compile_cpu_time=10 * 1000 * 1000 * 1000,
        compile_memory=512 * 1024 * 1024
    ),
    Language.CHECKER: LanguageConfig(
        name="checker",
        src_name="checker.cpp",
        exe_name="checker",
        compile_args=[
            "g++", "checker.cpp", "-o", "checker",
            "-O2", "-static", "-std=c++17"
        ],
        run_args=["./checker", "input.in", "output.out", "2"],
        compile_cpu_time=5 * 1000 * 1000 * 1000,
        compile_memory=512 * 1024 * 1024,
        env=["PATH=/usr/bin:/bin"],
    )
}

def get_language_config(lang_id: int) -> LanguageConfig:
    config = LANG_CONFIGS.get(lang_id)
    if not config:
        raise ValueError(f"Unsupported language ID: {lang_id}")
    return config
