# AI 引擎优化分析报告

> 日期：2026-06-25
> 对比项目：[vliang-chinesechess-cpp](https://github.com/RayZhhh/vliang-chinesechess-cpp) (C++ 中国象棋 AI)
> 优化策略：短期纯 Python 改进 + 中期 C++/pybind11 热路径重写

---

## 一、项目概况对比

| 维度 | 本项目 AI (Python) | vliang-chinesechess-cpp (C++) |
|------|-------------------|-------------------------------|
| **语言** | Python 3 | C++20 |
| **搜索深度上限** | 2~6 (难度 EASY→MASTER) | 6~8+ (i9-9880H 深8约3~5秒) |
| **性能** | 深3约2-3秒 (解释执行) | 深8约3-5秒 (编译 -O3)，Java版3倍速 |
| **代码规模** | `engine.py` ~984 行 | ~12个 .h/.cpp 文件 |
| **并行支持** | 无 | 多线程（每个候选着法独立线程） |
| **Python 接口** | 原生调用 | subprocess 可执行文件 + 输出文件 |

---

## 二、搜索算法对比

| 技术 | 本项目 | vliang-cpp | 差异 |
|------|--------|-----------|------|
| **基本框架** | Negamax | Max/Min 分离 Alpha-Beta | Negamax 更简洁 |
| **Alpha-Beta 剪枝** | ✅ 标准实现 | ✅ 标准 + 带记忆版本 | 功能等价 |
| **MTD(f) 搜索** | ❌ | ✅ 核心特色 | **vliang-cpp 重要优势** |
| **迭代深化** | ✅ depth 1→N | ✅ depth 2→N + 初始值估算 | vliang-cpp 利用上层结果更高效 |
| **静态清算搜索 (QS)** | ✅ 吃子扩展 | ✅ 吃子扩展 + 被将军时保留全着法 | vliang-cpp 对将军场景更安全 |
| **空着裁剪 (Null-Move)** | ✅ R=2 | ❌ | **本项目独有优势** |
| **置换表 (TT)** | ✅ `dict[(hash,turn,depth)]` | ✅ 双层置换表 + 双 Zobrist 校验 | vliang-cpp 防碰撞更可靠 |
| **Killer/历史启发** | ✅ 每层2个 + 历史表 | ✅ 着法排序 + TT 最优着法优先 | 本项目策略更丰富 |

### MTD(f) 算法要点

MTD(f) 通过反复调用零窗口 `[beta-1, beta]` Alpha-Beta 搜索来逐步收敛到真实值：

```
val = 初始猜测值
lowerBound = -∞, upperBound = +∞
while lowerBound < upperBound:
    beta = val + 1 if val == lowerBound else val
    val = AlphaBeta(beta-1, beta)  # 零窗口搜索
    if val < beta: upperBound = val
    else: lowerBound = val
```

相比全窗口迭代深化，通常减少 10-30% 节点访问量。

---

## 三、评估函数对比

| 维度 | 本项目 | vliang-cpp |
|------|--------|-----------|
| **位置价值表覆盖** | 3类：兵、车炮共用、马 | **7类全部**：帅/仕/炮/马/车/相/兵 |
| **阶段自适应** | ✅ `phase` 动态调整马/炮价值 + 位置权重 | ❌ 纯静态权重 |
| **活跃度加成** | ✅ 兵过河/中央、车中央/过河、马中央 | ❌ |
| **车辆极端位置标记** | ❌ | ✅ 含 `8888` 极端值标记致命位置 |
| **规则检测** | ✅ 长将/长捉/三次重复/50步 | ❌ README 明确"暂未处理" |

### 位置表差异影响

- vliang-cpp 对**炮、仕、相、帅**各有独立位置表，评估粒度明显更细
- 本项目独有的**阶段自适应 (phase-aware)** 动态权重非常值得保留
- 规则检测对实战对弈至关重要，vliang-cpp 缺失

---

## 四、C++ 实现 Python 库的方案评估

| 方案 | 难度 | 性能提升 | 维护成本 | 推荐度 |
|------|------|---------|---------|--------|
| **pybind11 绑定** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ **强烈推荐** |
| **Cython** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ 可选 |
| **subprocess 可执行文件** | ⭐ | ⭐⭐ | ⭐ | ⭐⭐ 不推荐 |
| **ctypes/cffi** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ 可选 |
| **原生 Python C API** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ 不推荐 |

### 推荐方案：pybind11 渐进式重写热路径

```
当前:
  room_manager.py → ai_proxy.py → engine.py (ChessAI)

优化后:
  room_manager.py → ai_proxy.py → engine.py (ChessAI, 规则检测+评估)
                                    → _cpp_negamax() (pybind11 C++ 搜索循环)
```

**原则**：保留 Python 的规则检测和评估函数，仅将递归搜索热路径 C++ 化。
原因：
- 评估函数逻辑复杂且变化多，Python 便于迭代
- 规则检测（长将/长捉/三次重复）不消耗大量 CPU
- 真正的性能瓶颈在 `_negamax()` 递归循环中

---

## 五、短期优化方案（已执行）

### 1. 引入 Zobrist 哈希

- 替代 `board_to_fen()` + dict 的 FEN 字符串方案
- `ZobristHasher` 已存在于 `chess/recorder.py`
- 用于置换表 key 和搜索路径重复检测，速度提升 ~100-1000x

### 2. 完善位置价值表（7类棋子全覆盖）

新增独立位置表：
- **炮**独立表（不同于车）：过河位置加分，中路肋道加权
- **仕/士**独立表：居中 > 边路，与帅配合
- **相/象**独立表：中路 > 边路，田字中心
- **帅/将**独立表：底线安全位置加权

### 3. 添加 MTD(f) 搜索

- 在 Negamax 基础上封装零窗口搜索
- 用浅搜索做初始值估算，加速收敛
- 预期效果：相同时间内搜索深度 +1

### 4. 优化静态清算搜索

- 将军时保留全部着法（包括非吃子逃避着法），避免误判
- 借鉴 vliang-cpp 的成熟做法

---

## 六、中期规划建议

| 序号 | 任务 | 预期效果 | 预估工作量 |
|------|------|---------|-----------|
| 1 | `pybind11` 绑定 C++ 搜索核心 | 速度提升 10-50x | 3-5 天 |
| 2 | 引入多线程根节点评估 | 多核 CPU 利用率提升 | 1-2 天 |
| 3 | 添加开局库（Zobrist key 索引） | 开局阶段省去搜索 | 2-3 天 |
| 4 | 残局库（可选） | 残局精确求解 | 5-7 天 |

---

## 七、总结

vliang-chinesechess-cpp 在 **MTD(f) 搜索、7类棋子位置表、Zobrist 双哈希、多线程评估** 方面值得借鉴，但其缺少规则检测和阶段自适应评估。

最优策略：**吸收算法精华改进当前 Python 引擎 + 规划热路径 C++/pybind11 渐进重写**。

---

> 本文档基于以下源码分析生成：
> - 本项目：`game-service/ai/engine.py`、`game-service/chess/recorder.py`
> - vliang-cpp：`cpp/source/alpha_beta.cpp`、`cpp/source/mtdf.cpp`、`cpp/source/quiescence.cpp`、`cpp/include/weights.h`、`cpp/include/chessboard.h`、`py_interface.cpp`
