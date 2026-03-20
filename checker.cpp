#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <sstream>
#include <algorithm>
#include <cstdio>

// 定义返回状态码
#define AC 0
#define PE 1
#define WA 2
#define OLE 3
#define ERROR 4

// 编译指令建议: g++ checker.cpp -o checker -O2 -std=c++17

/**
 * 检查如果用户输出正确答案然后又输出多余信息，判题结果是什么
 * 逻辑说明:
 * 1. OLE Check: 在读取 stdin 时实时检查，限制为 max(AnsSize * 2, AnsSize + 10MB)。
 * 2. Pre-process: 读取完成后，全局移除 '\r'，消除换行符差异。
 * 3. Strict Check: userString == ansString。
 * 4. Relaxed Check: 
 * - 按行分割。
 * - 每一行 trim 掉首尾空格 (中间空格保留)。
 * - 忽略空行。
 * - 逐行对比内容。
 */

// 辅助：移除字符串首尾空白
void trimLine(std::string &s) {
    if (s.empty()) return;
    // 找到第一个非空字符
    size_t first = s.find_first_not_of(" \t");
    if (first == std::string::npos) {
        s.clear(); // 全是空格
        return;
    }
    // 找到最后一个非空字符
    size_t last = s.find_last_not_of(" \t");
    s.erase(last + 1);      // 删除后缀
    s.erase(0, first);      // 删除前缀
}

// 辅助：获取用于宽松比较的行列表
// 逻辑：分割 -> Trim首尾 -> 丢弃空行 -> 存入Vector
std::vector<std::string> getRelaxedLines(const std::string& content) {
    std::vector<std::string> lines;
    std::stringstream ss(content);
    std::string line;
    while (std::getline(ss, line)) { // getline 默认以 \n 分割
        trimLine(line);
        if (!line.empty()) {
            lines.push_back(line);
        }
    }
    return lines;
}

int main(int argc, char* argv[]) {
    // 1. 基础设置与参数检查
    // 关闭同步以加速 IO
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    if (argc < 4) {
        // 需要: [0]程序名 [1]Input(忽略) [2]AnswerFile [3]Mode
        return ERROR;
    }

    std::string ansPath = argv[2];
    int mode = 0;
    try {
        mode = std::stoi(argv[3]);
    } catch (...) {
        return ERROR;
    }

    // 2. 读取标准答案 (Answer File)
    std::ifstream fAns(ansPath, std::ios::binary); // 二进制读取，保留原始 \r 以便后续手动处理
    if (!fAns) {
        return ERROR;
    }
    
    // 一次性读入 Answer
    fAns.seekg(0, std::ios::end);
    size_t ansSize = fAns.tellg();
    fAns.seekg(0, std::ios::beg);
    
    std::string sAns;
    sAns.resize(ansSize);
    fAns.read(&sAns[0], ansSize);
    fAns.close();

    // 3. 设定 OLE 阈值 (参考你的逻辑)
    // 允许 AnsSize * 2 或 AnsSize + 10MB
    size_t maxLimit = ansSize * 2;
    if (maxLimit < ansSize + 10 * 1024 * 1024) {
        maxLimit = ansSize + 10 * 1024 * 1024;
    }

    // 4. 读取用户输出 (从 Pipe / Stdin 读取)
    std::string sUser;
    sUser.reserve(ansSize + 1024); // 预分配一点内存
    
    char buffer[4096];
    while (std::cin.read(buffer, sizeof(buffer)) || std::cin.gcount() > 0) {
        size_t count = std::cin.gcount();
        // 实时 OLE 检查
        if (sUser.size() + count > maxLimit) {
            return OLE;
        }
        sUser.append(buffer, count);
    }

    // 5. 预处理：移除 Windows/Linux 换行符差异 (\r)
    // 这样 Strict 比较时，"123\n" 和 "123\r\n" 将变得完全一致
    auto stripCR = [](std::string& s) {
        s.erase(std::remove(s.begin(), s.end(), '\r'), s.end());
    };
    stripCR(sUser);
    stripCR(sAns);

    // 6. 执行判题逻辑
    bool isStrictMatch = (sUser == sAns);

    if (mode == 2) {
        // Mode 2: Strict First, then Relaxed -> PE/WA
        if (isStrictMatch) {
            return AC;
        }
        
        // Strict 失败，尝试 Relaxed
        std::vector<std::string> userLines = getRelaxedLines(sUser);
        std::vector<std::string> ansLines = getRelaxedLines(sAns);
        
        if (userLines == ansLines) {
            return PE; // 内容是对的，只是格式问题
        } else {
            return WA; // 内容彻底错了
        }
    } 
    else if (mode == 1) {
        // Mode 1: Ignore format (Relaxed check only)
        // 只要 Relaxed 通过就是 AC
        if (isStrictMatch) return AC; // 包含 strict 的情况肯定也是 AC

        std::vector<std::string> userLines = getRelaxedLines(sUser);
        std::vector<std::string> ansLines = getRelaxedLines(sAns);
        
        if (userLines == ansLines) {
            return AC;
        } else {
            return WA;
        }
    } 
    else {
        return ERROR;
    }
}



// #include <fstream>
// #include <string>
// #include <iostream>
// #include <algorithm>
// #include <sys/stat.h>
// #define AC 0
// #define PE 1
// #define WA 2
// #define OLE 3
// #define ERROR 4 //internal wrong
// /*

// 编译指令 g++ -std=c++17 -O2 -static -o checker checker.cpp
// ================================================================================
// Variant              | Total Time | Avg (ms)   | Bin Size (KB)   | vs Best   
// --------------------------------------------------------------------------------
// C++ O2 Static        | 4.4735     | 0.8947     | 2289.6          | +0.00  %
// C++ O3 Static        | 4.5083     | 0.9017     | 2289.5          | +0.78  %
// C O3                 | 5.3504     | 1.0701     | 16.1            | +19.60 %
// C++ O3 Dynamic       | 7.5352     | 1.5070     | 26.8            | +68.44 %
// C++ O2 Dynamic       | 8.2136     | 1.6427     | 26.9            | +83.61 %
// ================================================================================
// ================================================================================
// Variant                | Total Time | Avg (ms)   | Bin Size (KB)   | vs Best   
// --------------------------------------------------------------------------------
// C++17 O2 Static        | 4.2610     | 0.8522     | 2289.6          | +0.00  %
// C++11 O2 Native        | 4.2829     | 0.8566     | 2289.5          | +0.51  %
// C++17 O2 Native        | 4.2945     | 0.8589     | 2289.6          | +0.78  %
// C++17 O3 Native        | 4.3244     | 0.8649     | 2289.5          | +1.49  %
// C O3(Ref)Native        | 4.3269     | 0.8654     | 767.1           | +1.55  %
// C++11 O2 Static        | 4.3854     | 0.8771     | 2289.5          | +2.92  %
// ================================================================================
// */
// //可以考虑结果一旦不一致直接终止用户代码，提早结束 ,两种模式一种逐个测试点运行，一旦非ac直接结束，一种跑完所有测试点
// /**
//  * Usage: ./checker <user_file> <answer_file> <mode>
//  * * Arguments:
//  * user_file:   Path to the participant's output.
//  * answer_file: Path to the expected standard output.
//  * mode: 1 = Ignore trailing spaces and empty lines.
//  *       2 = Perform a strict comparison first. If it fails, perform a loose comparison; 
//  *           if that passes, return PE (Presentation Error), otherwise return WA (Wrong Answer).
//  * * Return Codes:
//  * 0: AC (Accepted) - Files match based on mode.
//  * 1: PE (Presentation Error) - Content matches but formatting differs.
//  * 2: WA (Wrong Answer) - Core content mismatch.
//  * 3：OLE(Output Limit Exceed)-Useroutput is too large
//  * 4:ERROR(Internal Error) -Not found file 
//  */

//  //仅Linux 平台可用
// long long getFileSize(const std::string&path)
// {
//     struct stat stat_buf;
//     if(stat(path.c_str(),&stat_buf)==0)
//     {
//         return stat_buf.st_size;
//     }
//     return -1;
// }
// void trimCR(std::string &s)
// {
//     if(!s.empty()&&s.back()=='\r')s.pop_back();
// }
// void trimAll(std::string &s)
// {
//     trimCR(s);
//     if(s.empty())return;
//     size_t first = s.find_first_not_of(" \t");
//     if(first == std::string::npos){
//         s.clear();
//         return;
//     }
//     size_t last = s.find_last_not_of(" \t");
//     //s = s.substr(first,(last-first+1));
//     s.erase(last+1);
//     s.erase(0,first);
// }
// bool checkStrict(std::ifstream& fUser, std::ifstream& fAns)
// {
//     fUser.clear(); fUser.seekg(0);
//     fAns.clear(); fAns.seekg(0);

//     // std::ifstream fUser(pathUser);
//     // std::ifstream fAns(pathAns);
//     if(!fUser||!fAns)return false;
//     std::string sUser,sAns;
//     while(true)
//     {
//         bool hasUser = static_cast<bool>(std::getline(fUser,sUser));
//         bool hasAns = static_cast<bool>(std::getline(fAns,sAns));
//         if(!hasAns && !hasUser)return true;
//         if(hasUser!=hasAns)return false;
//         trimCR(sUser);
//         trimCR(sAns);
//         if(sUser!=sAns)return false;
//     }

// }
// bool checkRelaxed(std::ifstream& fUser, std::ifstream& fAns)
// {
//     fUser.clear(); fUser.seekg(0);
//     fAns.clear(); fAns.seekg(0);
//     // std::ifstream fUser(pathUser);
//     // std::ifstream fAns(pathAns);
//     if(!fUser||!fAns)return false;
//     std::string sUser,sAns;
//     auto getNextValidLine = [&](std::ifstream&f,std::string& outStr)->bool{
//         while(std::getline(f,outStr))
//         {
//             trimAll(outStr);
//             if(!outStr.empty())return true;

//         }
//         return false;
//     };
//     while(true)
//     {
//         bool hasUser = getNextValidLine(fUser,sUser);
//         bool hasAns = getNextValidLine(fAns,sAns);
//         if(!hasUser&&!hasAns)return true;
//         if(hasUser!=hasAns)return false;
//         if(sUser!=sAns)return false;
//     }
// }
// int main(int argc,char* argv[])
// {
//     std::ios::sync_with_stdio(false);
//     std::cin.tie(nullptr);
//     if(argc<4)
//     {
//         return ERROR;
//     }
//     std::string userPath = argv[1];
//     std::string ansPath = argv[2];
//     int mode = 0;
//     try{
//         mode = std::stoi(argv[3]);
//     }catch(...){
//         return ERROR;
//     }
//     long long uSize = getFileSize(userPath);
//     long long aSize = getFileSize(ansPath);
//     if(uSize==-1||aSize==-1)return ERROR;

//     if(uSize>aSize + 10*1024*1024&&uSize>aSize*2)return OLE;

//     std::ifstream fUser(userPath),fAns(ansPath);
//     if(!fUser||!fAns)return ERROR;
    
//     //手动调整缓冲区对小文件io是负优化
//     // char bufferUser[65536], bufferAns[65536];
//     // fUser.rdbuf()->pubsetbuf(bufferUser, sizeof(bufferUser));
//     // fAns.rdbuf()->pubsetbuf(bufferAns, sizeof(bufferAns));

//     if(mode==1)
//     {
//         if(checkRelaxed(fUser,fAns))return AC;
//         return WA;
//     }
//     else if(mode==2)
//     {
//         if(checkStrict(fUser,fAns))return AC;
//         if(checkRelaxed(fUser,fAns))return PE;
//         return WA;
//     }
//     else{
//         return ERROR;
//     }
    
// }
// /*
// User Output (用_代表空格)	Standard Answer	模式	判定结果	原因
// 123 (Linux \n)	123 (Windows \r\n)	2 (Strict)	AC	代码已做 trimCR 兼容处理
// 123_ (末尾多空格)	123	2 (Strict)	PE	Strict 失败(空格不同), Relaxed 成功
// _123 (首部多空格)	123	2 (Strict)	PE	Strict 失败, Relaxed 成功
// 1__2 (中间多空格)	1_2	2 (Strict)	WA	中间空格被视为内容，Relaxed 也不通过
// 123\n\n (多空行)	123	2 (Strict)	PE	Strict 行数不同，Relaxed 忽略空行
// 123_	123	1 (Relaxed)	AC	宽松模式忽略首尾空格
// 123\n\n	123	1 (Relaxed)	AC	宽松模式忽略多余空行
// */