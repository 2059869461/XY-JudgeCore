from enum import Enum
from pydantic import BaseModel, Field
from typing import Union

# --- Enums ---

class Status(str, Enum):
    Accepted = 'Accepted'
    MemoryLimitExceeded = 'Memory Limit Exceeded'
    TimeLimitExceeded = 'Time Limit Exceeded'
    OutputLimitExceeded = 'Output Limit Exceeded'
    FileError = 'File Error'
    NonzeroExitStatus = 'Nonzero Exit Status'
    Signalled = 'Signalled'
    InternalError = 'Internal Error'

class FileErrorType(str, Enum):
    CopyInOpenFile = 'CopyInOpenFile'
    CopyInCreateFile = 'CopyInCreateFile'
    CopyInCopyContent = 'CopyInCopyContent'
    CopyOutOpen = 'CopyOutOpen'
    CopyOutNotRegularFile = 'CopyOutNotRegularFile'
    CopyOutSizeExceeded = 'CopyOutSizeExceeded'
    CopyOutCreateFile = 'CopyOutCreateFile'
    CopyOutCopyContent = 'CopyOutCopyContent'
    CollectSizeExceeded = 'CollectSizeExceeded'

# --- File Definitions ---

class LocalFile(BaseModel):
    src: str

class MemoryFile(BaseModel):
    content: str | bytes

class PreparedFile(BaseModel):
    fileId: str

class Collector(BaseModel):
    name: str
    max: int
    pipe: bool | None = False

class Symlink(BaseModel):
    symlink: str

class StreamIn(BaseModel):
    streamIn: bool

class StreamOut(BaseModel):
    streamOut: bool

# --- Command & Request ---

CmdFile = Union[LocalFile, MemoryFile, PreparedFile, Collector, StreamIn, StreamOut, None]#stdin stdout stderr
CopyInFile = Union[LocalFile, MemoryFile, PreparedFile, Symlink]#copy进入容器的文件

class Cmd(BaseModel):
    args: list[str]
    env: list[str] | None = None
    files: list[CmdFile] | None = None
    tty: bool | None = None
    
    cpuLimit: int | None = None
    clockLimit: int | None = None
    memoryLimit: int | None = None
    stackLimit: int | None = None
    procLimit: int | None = None
    cpuRateLimit: int | None = None
    cpuSetLimit: str | None = None
    strictMemoryLimit: bool | None = None
    dataSegmentLimit: bool | None = None
    addressSpaceLimit: bool | None = None

    copyIn: dict[str, CopyInFile] | None = None
    copyOut: list[str] | None = None
    copyOutCached: list[str] | None = None
    copyOutMax: int | None = None
    copyOutTruncate: bool | None = None

class PipeIndex(BaseModel):
    index: int
    fd: int

class PipeMap(BaseModel):
    in_pos: PipeIndex = Field(...,serialization_alias="in")
    out: PipeIndex
    proxy: bool | None = None
    name: str | None = None
    max: int | None = None

    

class Request(BaseModel):
    requestId: str | None = None
    cmd: list[Cmd]
    pipeMapping: list[PipeMap] | None = None

# --- Response & Results ---

class FileError(BaseModel):
    name: str
    type: FileErrorType
    message: str | None = None

class Result(BaseModel):
    status: Status
    error: str | None = None
    exitStatus: int
    time: int
    memory: int
    procPeak: int | None = None
    runTime: int
    files: dict[str, str] | None = None
    fileIds: dict[str, str] | None = None
    fileError: list[FileError] | None = None

class WSResult(BaseModel):
    requestId: str
    results: list[Result]
    error: str | None = None

# --- WebSocket & Streaming ---

class CancelRequest(BaseModel):
    cancelRequestId: str

WSRequest = Union[Request, CancelRequest]

class Resize(BaseModel):
    index: int
    fd: int
    rows: int
    cols: int
    x: int
    y: int

class Input(BaseModel):
    index: int
    fd: int
    content: bytes

class Output(BaseModel):
    index: int
    fd: int
    content: bytes