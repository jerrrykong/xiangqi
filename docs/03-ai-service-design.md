# AI 服务详细设计（Python）

> 服务职责：AlphaZero 风格神经网络 + MCTS 搜索 + 自对弈数据生成 + 模型训练
> 技术栈：Python 3.11+ / PyTorch / NumPy
> 文档版本：v1.0

---

## 一、项目结构

```
ai-service/
├── model/
│   ├── __init__.py
│   ├── chess_net.py           # AlphaZero 神经网络（ChessNet）
│   ├── res_block.py          # 残差块（ResBlock）
│   └── policy_head.py         # 策略头（PolicyHead）
│   ├── value_head.py          # 价值头（ValueHead）
│   └── init_weights.py        # 网络权重初始化
├── mcts/
│   ├── __init__.py
│   ├── node.py               # MCTS 树节点（MCTSNode）
│   ├── search.py             # MCTS 主搜索算法
│   ├── uct.py                # UCT/UCB 公式
│   └── parallel.py           # 并行 MCTS
├── selfplay/
│   ├── __init__.py
│   ├── game.py               # 自对弈游戏（SelfPlayGame）
│   ├── buffer.py             # Replay Buffer
│   └── sampler.py            # 数据采样器
├── training/
│   ├── __init__.py
│   ├── trainer.py            # 训练循环主逻辑
│   ├── optimizer.py          # 优化器配置
│   ├── lr_schedule.py       # 学习率调度
│   ├── checkpoint.py         # 模型保存/加载
│   └── evaluator.py          # Elo 验证评估器
├── encoder/
│   ├── __init__.py
│   ├── board_encoder.py      # 棋盘特征编码（→ 张量）
│   ├── move_encoder.py       # 着法编码（→ 索引）
│   └── augment.py            # 数据增强（棋盘翻转）
├── engine/
│   ├── __init__.py
│   ├── engine.py            # 推理引擎（加载模型 + MCTS）
│   └── batch_engine.py       # 批量推理（多 GPU 支持）
├── data/
│   ├── dataset.py           # PyTorch Dataset
│   └── transforms.py        # 数据预处理
├── config.py                 # 配置
├── train.py                  # 训练入口脚本
├── selfplay_runner.py        # 自对弈入口脚本
└── requirements.txt
```

---

## 二、核心数据结构

### 2.1 MCTSNode（MCTS 树节点）

```python
# mcts/node.py
import math
from dataclasses import dataclass
from chess.move import Move

@dataclass
class MCTSNode:
    """
    MCTS 树的一个节点
    """
    # 状态
    visit_count: int = 0       # N(s,a) 访问次数
    value_sum: float = 0.0     # Σ Q(s,a) × N(s,a)
    prior: float = 0.0         # P(s,a) 神经网络输出的先验概率

    # 棋盘状态（在父节点执行 move 后得到）
    board: 'Board' = None      # 当前局面的棋盘
    move: Move | None = None  # 产生此节点的着法

    # 子节点
    children: dict[Move, 'MCTSNode'] | None = None  # 展开后

    @property
    def q_value(self) -> float:
        """平均价值 Q(s,a)"""
        if self.visit_count == 0:
            return 0.0
        return self.value_sum / self.visit_count

    def is_expanded(self) -> bool:
        return self.children is not None

    def is_terminal(self) -> bool:
        """是否为终局节点"""
        return self.board.is_checkmate() or self.board.is_stalemate()
```

### 2.2 MCTSResult（推理结果）

```python
# mcts/search.py
from dataclasses import dataclass
from chess.move import Move
import numpy as np

@dataclass
class MCTSResult:
    """
    MCTS 搜索结果
    """
    # 各着法的访问次数分布（归一化为概率）
    action_probs: np.ndarray   # shape: (num_moves,) 或 (num_slots,)

    # 局面评估（当前玩家视角的胜率）
    value: float               # -1.0 ~ 1.0

    # 最佳着法
    best_move: Move

    # 搜索统计
    total_visits: int
    search_time_ms: float

    def get_move_with_temperature(self, temperature: float = 1.0) -> Move:
        """
        带温度的着法采样
        temperature → 0：选择访问最多的着法（确定性）
        temperature → ∞：接近均匀随机
        """
        if temperature < 0.01:
            return self.best_move

        # 访问次数的 softmax
        probs = self.action_probs ** (1.0 / temperature)
        probs /= probs.sum()
        idx = np.random.choice(len(probs), p=probs)
        return self.best_move  # TODO: 映射回 Move
```

### 2.3 SelfPlayGame（自对弈存档）

```python
# selfplay/game.py
from dataclasses import dataclass
import numpy as np
from chess.move import Move

@dataclass
class SelfPlayGame:
    """
    一局自对弈的完整数据
    """
    game_id: str
    model_version: str
    moves: list[Move]

    # 每步的 NN 输出（策略 + 价值）— 用于训练
    policy_history: list[np.ndarray] = None  # 每步的 π (MCTS 访问次数归一化)
    value_history: list[float] = None        # 每步的价值（终局结果 z）
    result: int = 0                          # +1=红胜, -1=黑胜, 0=和棋

    def to_training_examples(self) -> list[dict]:
        """
        转换为训练样本
        返回 list[{
            "features": (18, 10, 9) 张量,
            "policy": 着法概率向量,
            "value": 胜率标签
        }]
        """
        examples = []
        n = len(self.moves)

        for i, (board, pi, _) in enumerate(zip(
            self.board_states, self.policy_history, range(n)
        )):
            # 终局结果（从当前玩家视角）
            if self.result == 1:
                z = 1.0 if i % 2 == 0 else -1.0  # 红方胜
            elif self.result == -1:
                z = -1.0 if i % 2 == 0 else 1.0  # 黑方胜
            else:
                z = 0.0

            examples.append({
                "features": board,
                "policy": pi,
                "value": z,
            })

        return examples
```

### 2.4 ReplayBuffer（数据缓冲池）

```python
# selfplay/buffer.py
import numpy as np
from collections import deque
import random
from selfplay.game import SelfPlayGame

class ReplayBuffer:
    """
    存储历史自对弈数据，支持均匀采样
    """

    def __init__(self, capacity: int = 100_000):
        self.capacity = capacity
        self.buffer: deque[SelfPlayGame] = deque(maxlen=capacity)
        self.total_games: int = 0

    def append(self, game: SelfPlayGame):
        self.buffer.append(game)
        self.total_games += 1

    def sample(self, batch_size: int) -> list[dict]:
        """
        均匀采样一个 batch 的训练样本
        """
        if len(self.buffer) == 0:
            return []

        # 随机选 N 局
        games = random.sample(list(self.buffer), min(batch_size, len(self.buffer)))
        examples = []

        for game in games:
            if len(game.board_states) == 0:
                continue
            ex = random.choice(game.to_training_examples())
            examples.append(ex)

        return examples[:batch_size]

    def size(self) -> int:
        return len(self.buffer)

    def summary(self) -> dict:
        return {
            "buffer_games": len(self.buffer),
            "total_games": self.total_games,
            "capacity": self.capacity,
            "fill_rate": len(self.buffer) / self.capacity,
        }
```

---

## 三、AlphaZero 神经网络

### 3.1 整体架构

```
输入: (batch, 18, 10, 9) 棋盘特征张量
        │
        ▼
┌─────────────────────┐
│   InputConv (Conv2D) │  18ch → 256ch, 3×3, ReLU
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    ResBlock × 19    │  ×19 个残差块（256ch, 3×3, BN, ReLU）
│  (Conv2D+BN+ReLU×2) │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌────────┐   ┌────────┐
│PolicyHead│   │ValueHead│
│  (策略) │   │  (价值) │
└────┬───┘   └────┬───┘
     │            │
     ▼            ▼
(9×9×9=729)    (1) 胜率
  着法概率      -1~1
```

### 3.2 ChessNet 实现

```python
# model/chess_net.py
import torch
import torch.nn as nn
import torch.nn.functional as F

class ResBlock(nn.Module):
    """残差块"""
    def __init__(self, channels: int = 256):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x):
        residual = x
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.bn2(self.conv2(x))
        x = F.relu(x + residual)
        return x


class PolicyHead(nn.Module):
    """策略头 — 输出每个着法的概率"""

    def __init__(self, in_channels: int = 256, num_moves: int = 2085):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, 2, 1, bias=False)  # 压缩到 2 通道
        self.bn = nn.BatchNorm2d(2)
        # 全连接层输出所有可能的着法
        self.fc = nn.Linear(2 * 10 * 9, num_moves)

    def forward(self, x):
        x = F.relu(self.bn(self.conv(x)))
        x = x.view(x.size(0), -1)
        x = self.fc(x)
        return F.log_softmax(x, dim=-1)  # log_softmax 便于 NLLLoss


class ValueHead(nn.Module):
    """价值头 — 预测胜率"""

    def __init__(self, in_channels: int = 256, hidden_dim: int = 256):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, 1, 1, bias=False)
        self.bn = nn.BatchNorm2d(1)
        self.fc1 = nn.Linear(10 * 9, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, 1)

    def forward(self, x):
        x = F.relu(self.bn(self.conv(x)))
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = torch.tanh(self.fc2(x))  # -1 ~ 1
        return x.squeeze(-1)


class ChessNet(nn.Module):
    """
    AlphaZero 风格中国象棋神经网络
    输入: (batch, 18, 10, 9) 棋盘特征
    输出: (policy: batch × num_moves, value: batch)
    """

    def __init__(
        self,
        in_channels: int = 18,
        residual_channels: int = 256,
        num_res_blocks: int = 19,
        num_moves: int = 2085,
    ):
        super().__init__()

        # 输入卷积
        self.input_conv = nn.Sequential(
            nn.Conv2d(in_channels, residual_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(residual_channels),
            nn.ReLU(),
        )

        # 残差塔
        self.res_tower = nn.ModuleList([
            ResBlock(residual_channels) for _ in range(num_res_blocks)
        ])

        # 策略头和价值头
        self.policy_head = PolicyHead(residual_channels, num_moves)
        self.value_head = ValueHead(residual_channels)

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: (batch, 18, 10, 9) 棋盘特征张量
        Returns:
            policy: (batch, num_moves) log 概率
            value: (batch,)  胜率预测 -1~1
        """
        x = self.input_conv(x)
        for res_block in self.res_tower:
            x = res_block(x)
        policy = self.policy_head(x)
        value = self.value_head(x)
        return policy, value

    def inference(self, x: torch.Tensor) -> tuple[np.ndarray, float]:
        """推理接口（单局面）"""
        self.eval()
        with torch.no_grad():
            x = torch.FloatTensor(x).unsqueeze(0)
            log_pi, v = self.forward(x)
            pi = torch.exp(log_pi).numpy()[0]  # 转为概率
            value = float(v.item())
        return pi, value
```

### 3.3 损失函数

```python
# training/trainer.py
def alphazero_loss(
    policy_logits: torch.Tensor,    # (batch, num_moves) 预测策略
    policy_target: torch.Tensor,   # (batch, num_moves) 目标策略（π）
    value_pred: torch.Tensor,       # (batch,) 预测价值
    value_target: torch.Tensor,    # (batch,) 目标价值（z）
    l2_reg: float = 1e-4,
) -> torch.Tensor:
    """
    AlphaZero 损失函数：
    L = (z - v)² - π·log(p) + λ||θ||²
    """
    # 价值损失
    value_loss = F.mse_loss(value_pred, value_target)

    # 策略损失（NLL）
    policy_loss = F.nll_loss(policy_logits, policy_target.argmax(dim=-1))

    # L2 正则化
    l2 = l2_reg * sum(p.pow(2).sum() for p in model.parameters())

    return value_loss + policy_loss + l2
```

---

## 四、MCTS 搜索算法

### 4.1 UCT 公式

```
选择阶段（Selection）：

对于每个节点，选择使得 UCB 最大的子节点：

    UCB(s, a) = Q(s, a) + Cpuct · P(s, a) · √(Σ N(s,·)) / (1 + N(s, a))

其中：
  - Q(s,a) = W(s,a) / N(s,a)  （平均价值）
  - Cpuct = 1.38              （探索常数，参考 AlphaZero 论文）
  - P(s,a)                    （NN 输出的先验概率）
  - N(s,·) = Σ N(s,a)         （父节点总访问次数）
```

### 4.2 MCTS 主算法

```python
# mcts/search.py
import math
import numpy as np
from chess.board import Board
from chess.piece import Color
from mcts.node import MCTSNode
from model.chess_net import ChessNet
from encoder.board_encoder import encode_board

class MCTS:
    """
    单线程 MCTS 搜索实现
    """

    def __init__(
        self,
        model: ChessNet,
        cpuct: float = 1.38,
    ):
        self.model = model
        self.cpuct = cpuct

    def search(
        self,
        board: Board,
        color: Color,
        n_simulations: int,
    ) -> MCTSResult:
        """
        执行 MCTS 搜索

        Args:
            board: 当前棋盘状态
            color: 当前玩家颜色
            n_simulations: 模拟次数

        Returns:
            MCTSResult: 搜索结果
        """
        root = MCTSNode(board=board.copy())
        root.expand(color, self.model)

        for _ in range(n_simulations):
            node = root
            path = [node]  # 记录搜索路径

            # ===== Selection =====
            # 从根节点开始，选择 UCB 最大的子节点，直到叶节点
            while node.is_expanded():
                node = self._select_child(node, color)
                path.append(node)

            # ===== Expansion + Evaluation =====
            # 如果不是终局，展开子节点并用 NN 评估
            if not node.is_terminal():
                node.expand(color, self.model)

            # ===== Backpropagation =====
            # 从叶节点向根节点回传价值
            value = self._evaluate(node, color)
            self._backpropagate(path, value, color)

        # 从根节点提取结果
        return self._get_result(root)

    def _select_child(self, node: MCTSNode, perspective: Color) -> MCTSNode:
        """
        UCB 最大的子节点
        """
        best_score = -float('inf')
        best_child = None

        for move, child in node.children.items():
            q = child.q_value if perspective == Color.RED else -child.q_value
            # 视角：红方最大化，黑方最小化
            score = q + self.cpuct * child.prior * math.sqrt(node.visit_count) / (1 + child.visit_count)
            if score > best_score:
                best_score = score
                best_child = child

        return best_child

    def _evaluate(self, node: MCTSNode, perspective: Color) -> float:
        """
        评估叶节点：
        - 终局：返回 ±1
        - 其他：用 NN 评估
        """
        if node.is_terminal():
            result = node.board.get_result()
            if result == 1:
                return 1.0 if perspective == Color.RED else -1.0
            elif result == -1:
                return -1.0 if perspective == Color.RED else 1.0
            else:
                return 0.0

        # NN 评估（棋盘编码 → 张量 → NN → 价值）
        features = encode_board(node.board.grid)
        _, value = self.model.inference(features)
        return value

    def _backpropagate(self, path: list[MCTSNode], value: float, perspective: Color):
        """从叶节点向根回传，更新访问次数和价值"""
        for node in reversed(path):
            node.visit_count += 1
            node.value_sum += value if perspective == Color.RED else -value

    def _get_result(self, root: MCTSNode) -> MCTSResult:
        """从根节点提取着法概率分布和最佳着法"""
        visits = np.array([
            child.visit_count for child in root.children.values()
        ], dtype=np.float32)
        moves = list(root.children.keys())

        # 归一化为概率
        if visits.sum() > 0:
            probs = visits / visits.sum()
        else:
            probs = np.ones(len(visits)) / len(visits)

        # 访问最多的着法
        best_idx = visits.argmax()
        best_move = moves[best_idx]

        return MCTSResult(
            action_probs=probs,
            value=-root.q_value,  # 根节点的 Q 值
            best_move=best_move,
            total_visits=root.visit_count,
            search_time_ms=0.0,
        )


def MCTSNode_expand(node: MCTSNode, color: Color, model: ChessNet):
    """展开节点 — 用 NN 预测所有合法着法的先验概率"""
    from chess.move_generator import MoveGenerator

    gen = MoveGenerator(node.board)
    legal_moves = gen.generate_all_moves(color)

    if not legal_moves:
        node.children = {}
        return

    # 编码棋盘
    features = encode_board(node.board.grid)

    # NN 推理
    with torch.no_grad():
        features_t = torch.FloatTensor(features).unsqueeze(0)
        log_pi, _ = model(features_t)
        pi = torch.exp(log_pi).numpy()[0]  # shape: (num_moves,)

    # 映射到合法着法
    children = {}
    priors = []
    for move in legal_moves:
        idx = move_to_idx(move)
        prior = max(pi[idx], 1e-6)  # 防止为 0
        priors.append(prior)

        child_board = node.board.copy()
        child_board.apply_move(move)

        child = MCTSNode(
            board=child_board,
            move=move,
            prior=prior,
        )
        children[move] = child

    # 归一化先验概率
    total = sum(priors)
    for move in children:
        children[move].prior /= total

    node.children = children
```

### 4.3 并行 MCTS（提升推理速度）

```python
# mcts/parallel.py
import concurrent.futures

class ParallelMCTS:
    """
    并行 MCTS — 多线程同时搜索不同分支
    线程数建议 = CPU 核心数
    """

    def __init__(self, model: ChessNet, num_workers: int = 4):
        self.model = model
        self.num_workers = num_workers
        self.single_mcts = MCTS(model)

    def search(self, board: Board, color: Color, n_simulations: int) -> MCTSResult:
        sims_per_worker = n_simulations // self.num_workers

        roots = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = [
                executor.submit(self.single_mcts.search, board.copy(), color, sims_per_worker)
                for _ in range(self.num_workers)
            ]
            roots = [f.result() for f in futures]

        # 合并结果：访问次数加权
        combined_visits = np.zeros_like(roots[0].action_probs)
        for result in roots:
            combined_visits += result.action_probs * result.total_visits

        combined_visits /= sum(r.total_visits for r in roots)

        return MCTSResult(
            action_probs=combined_visits,
            value=roots[0].value,
            best_move=roots[0].best_move,
            total_visits=n_simulations,
            search_time_ms=0.0,
        )
```

---

## 五、棋盘特征编码

### 5.1 encode_board

```python
# encoder/board_encoder.py
import torch
import numpy as np
from chess.board import Board

# 通道定义
CH_RED_ROOK    = 0
CH_RED_KNIGHT  = 1
CH_RED_BISHOP  = 2
CH_RED_ADVISOR = 3
CH_RED_KING    = 4
CH_RED_PAWN    = 5
CH_BLACK_ROOK  = 6
CH_BLACK_KNIGHT = 7
CH_BLACK_BISHOP = 8
CH_BLACK_ADVISOR= 9
CH_BLACK_KING   = 10
CH_BLACK_PAWN   = 11
CH_TURN         = 12
CH_HISTORY_1    = 13
CH_HISTORY_2    = 14
CH_RED_PALACE   = 15
CH_BLACK_PALACE = 16
CH_CROSSED      = 17

TOTAL_CHANNELS = 18

def encode_board(board: list[list[int]]) -> np.ndarray:
    """
    将棋盘编码为 (18, 10, 9) 张量
    """
    tensor = np.zeros((TOTAL_CHANNELS, Board.ROWS, Board.COLS), dtype=np.float32)

    red_palace_mask = np.zeros((Board.ROWS, Board.COLS), dtype=np.float32)
    red_palace_mask[7:11, 3:6] = 1.0

    black_palace_mask = np.zeros((Board.ROWS, Board.COLS), dtype=np.float32)
    black_palace_mask[0:3, 3:6] = 1.0

    for r in range(Board.ROWS):
        for c in range(Board.COLS):
            code = board[r][c]
            if code == 0:
                continue

            color = code // 10
            ptype = code % 10

            if color == 1:  # 红方
                ch_map = {4: CH_RED_ROOK, 3: CH_RED_KNIGHT, 2: CH_RED_BISHOP,
                          1: CH_RED_ADVISOR, 0: CH_RED_KING, 6: CH_RED_PAWN}
                tensor[ch_map[ptype], r, c] = 1.0
            elif color == 2:  # 黑方
                ch_map = {4: CH_BLACK_ROOK, 3: CH_BLACK_KNIGHT, 2: CH_BLACK_BISHOP,
                          1: CH_BLACK_ADVISOR, 0: CH_BLACK_KING, 6: CH_BLACK_PAWN}
                tensor[ch_map[ptype], r, c] = 1.0

    tensor[CH_RED_PALACE] = red_palace_mask
    tensor[CH_BLACK_PALACE] = black_palace_mask

    return tensor  # shape: (18, 10, 9)


def encode_board_tensor(board: list[list[int]]) -> torch.Tensor:
    """返回 PyTorch 张量"""
    return torch.FloatTensor(encode_board(board))
```

---

## 六、自对弈流程

### 6.1 SelfPlayGame（单局自对弈）

```python
# selfplay/game.py
import uuid
import numpy as np
from chess.board import Board
from chess.piece import Color
from mcts.search import MCTS
from encoder.board_encoder import encode_board

class SelfPlayGame:

    def __init__(self, model: MCTS, model_version: str, temperature: float = 1.0):
        self.game_id = str(uuid.uuid4())
        self.model_version = model_version
        self.temperature = temperature

        self.board = Board()
        self.current_color = Color.RED
        self.mcts = model

        self.board_states: list[np.ndarray] = []  # 局面特征历史
        self.policy_history: list[np.ndarray] = []  # 策略历史
        self.value_history: list[float] = []     # 价值历史

    def run(self) -> 'SelfPlayGame':
        """运行完整一局自对弈"""
        while not self.board.is_game_over():
            # 记录当前局面
            features = encode_board(self.board.grid)
            self.board_states.append(features)

            # MCTS 搜索
            result = self.mcts.search(
                self.board,
                self.current_color,
                n_simulations=800,
            )

            # 带温度采样着法
            move = self._sample_move(result)
            self.policy_history.append(result.action_probs)

            # 执行着法
            self.board.apply_move(move)

            # 切换玩家
            self.current_color = self.current_color.opposite

        # 记录终局价值
        final_value = self._get_final_value()
        self.value_history = [final_value] * len(self.board_states)
        self.result = int(final_value)  # +1, -1, 0

        return self

    def _sample_move(self, result: MCTSResult) -> 'Move':
        """根据温度参数采样着法"""
        if self.temperature < 0.01:
            return result.best_move

        probs = result.action_probs ** (1.0 / self.temperature)
        probs /= probs.sum()
        idx = np.random.choice(len(probs), p=probs)

        # idx → Move（需要维护一个合法的 idx→Move 映射）
        return self.mcts.idx_to_move(idx)

    def _get_final_value(self) -> float:
        result = self.board.get_result()
        return float(result)  # +1, -1, 0
```

### 6.2 自对弈主循环

```python
# selfplay_runner.py
import asyncio
import logging
from datetime import datetime

from selfplay.buffer import ReplayBuffer
from selfplay.game import SelfPlayGame
from mcts.search import MCTS, ParallelMCTS
from model.chess_net import ChessNet

logger = logging.getLogger(__name__)


class SelfPlayRunner:

    def __init__(self, model: ChessNet, buffer: ReplayBuffer, config):
        self.buffer = buffer
        self.config = config

        # 推理引擎
        self.mcts = MCTS(model, cpuct=1.38)

    async def run_batch(self, num_games: int):
        """
        运行一批自对弈
        """
        for i in range(num_games):
            game = SelfPlayGame(
                model=self.mcts,
                model_version=self.config.MODEL_VERSION,
                temperature=1.0,  # 初期温度高（更多探索）
            )

            # 在线程池中运行（不阻塞事件循环）
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, game.run)

            self.buffer.append(game)
            logger.info(f"Game {i+1}/{num_games} done. "
                        f"Result: {game.result}. Buffer size: {self.buffer.size()}")
```

---

## 七、训练流程

### 7.1 Trainer（训练循环）

```python
# training/trainer.py
import torch
import torch.optim as optim
from torch.utils.data import DataLoader
from datetime import datetime

from model.chess_net import ChessNet, alphazero_loss
from selfplay.buffer import ReplayBuffer
from encoder.board_encoder import encode_board_tensor
from training.checkpoint import CheckpointManager
from training.lr_schedule import WarmupScheduler

class Trainer:

    def __init__(self, model: ChessNet, buffer: ReplayBuffer, config):
        self.model = model
        self.buffer = buffer
        self.config = config

        self.optimizer = optim.Adam(
            model.parameters(),
            lr=config.LR,
            weight_decay=config.WEIGHT_DECAY,
        )

        self.scheduler = WarmupScheduler(
            self.optimizer,
            warmup_steps=config.WARMUP_STEPS,
            total_steps=config.TOTAL_STEPS,
        )

        self.checkpoint = CheckpointManager(config.CHECKPOINT_DIR)

    def train_step(self, batch: dict) -> dict:
        """单步训练"""
        features = torch.FloatTensor(batch["features"])  # (B, 18, 10, 9)
        policy_target = torch.LongTensor(batch["policy_idx"])  # (B,)
        value_target = torch.FloatTensor(batch["value"])  # (B,)

        self.optimizer.zero_grad()

        policy_logits, value_pred = self.model(features)
        loss = alphazero_loss(policy_logits, None, value_pred, value_target)

        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()

        return {
            "loss": loss.item(),
            "lr": self.optimizer.param_groups[0]["lr"],
        }

    def train_epoch(self, epoch: int):
        """一个 epoch"""
        dataset = SelfPlayDataset(self.buffer)
        loader = DataLoader(dataset, batch_size=32, shuffle=True, num_workers=4)

        total_loss = 0.0
        for batch in loader:
            stats = self.train_step(batch)
            total_loss += stats["loss"]

        avg_loss = total_loss / len(loader)
        logger.info(f"Epoch {epoch}: avg_loss={avg_loss:.4f}")
        return avg_loss

    def train(self):
        """完整训练循环"""
        step = 0
        best_loss = float('inf')

        while step < self.config.TOTAL_STEPS:
            # 1. 自对弈生成数据
            if self.buffer.size() < self.config.MIN_BUFFER_SIZE:
                logger.info("Buffer too small, running self-play...")
                self.selfplay_runner.run_batch(self.config.GAMES_PER_ITER)

            # 2. 训练 N 步
            for _ in range(self.config.TRAINING_STEPS_PER_ITER):
                self.train_step(self.buffer.sample(self.config.BATCH_SIZE))
                step += 1

                # 学习率调度
                self.scheduler.step()

                # 日志
                if step % 100 == 0:
                    logger.info(f"Step {step}: lr={self.optimizer.param_groups[0]['lr']:.6f}")

            # 3. 保存 checkpoint
            if step % self.config.SAVE_INTERVAL == 0:
                self.checkpoint.save(self.model, step, self.optimizer)

            # 4. 评估（Elo 对比）
            if step % self.config.EVAL_INTERVAL == 0:
                new_elo = self.evaluator.evaluate(self.model)
                if new_elo > self.config.BASELINE_ELO:
                    logger.info(f"New model Elo {new_elo} > baseline, publishing...")
                    self.publish_model()
```

### 7.2 学习率调度（Warmup + Cosine）

```python
# training/lr_schedule.py
import math

class WarmupScheduler:

    def __init__(self, optimizer, warmup_steps: int, total_steps: int,
                 lr_max: float = 1e-3, lr_min: float = 1e-5):
        self.optimizer = optimizer
        self.warmup_steps = warmup_steps
        self.total_steps = total_steps
        self.lr_max = lr_max
        self.lr_min = lr_min
        self.step_count = 0

    def step(self):
        self.step_count += 1
        lr = self._get_lr()
        for param_group in self.optimizer.param_groups:
            param_group["lr"] = lr

    def _get_lr(self) -> float:
        if self.step_count <= self.warmup_steps:
            # Warmup 阶段：线性增长
            return self.lr_max * self.step_count / self.warmup_steps
        else:
            # Cosine 衰减阶段
            progress = (self.step_count - self.warmup_steps) / (
                self.total_steps - self.warmup_steps
            )
            return self.lr_min + 0.5 * (self.lr_max - self.lr_min) * (
                1 + math.cos(math.pi * progress)
            )
```

### 7.3 模型评估（Elo 对比）

```python
# training/evaluator.py
class ModelEvaluator:

    def __init__(self, baseline_model: ChessNet, num_games: int = 200):
        self.baseline = baseline_model
        self.num_games = num_games

    async def evaluate(self, new_model: ChessNet) -> float:
        """
        新模型 vs 旧模型 Elo 对比评测
        返回新模型的 Elo 评分
        """
        wins = 0
        losses = 0
        draws = 0

        for i in range(self.num_games):
            # 随机决定执红还是执黑
            if i % 2 == 0:
                red_model, black_model = new_model, self.baseline
            else:
                red_model, black_model = self.baseline, new_model

            result = self._play_game(red_model, black_model)
            if result == 1:
                wins += 1
            elif result == -1:
                losses += 1
            else:
                draws += 1

        # 计算新模型 Elo（假设旧模型 Elo = 基准）
        score = (wins + 0.5 * draws) / self.num_games
        expected_score = 1 / (1 + 10 ** ((1800 - 0) / 400))  # 简化计算
        new_elo = 1800 + 400 * (score - expected_score) / (1 - expected_score)

        logger.info(f"Eval: {wins}W/{draws}D/{losses}L, new Elo: {new_elo:.0f}")
        return new_elo

    def _play_game(self, red_model, black_model) -> int:
        """快速对局（用于评估）"""
        # 同 SelfPlayGame，但用较少模拟次数（200 次）
        ...
```

---

## 八、推理引擎（生产部署）

### 8.1 推理引擎接口

```python
# engine/engine.py
import torch
import numpy as np
from chess.board import Board
from model.chess_net import ChessNet
from mcts.search import MCTS
from encoder.board_encoder import encode_board_tensor
from chess.move import Move

class AIEngine:

    def __init__(self, model_path: str, device: str = "cpu"):
        self.device = device
        self.model = ChessNet()
        self.load_model(model_path)
        self.mcts = MCTS(self.model)

    def load_model(self, model_path: str):
        """加载模型权重"""
        state_dict = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
        self.model.to(self.device)
        self.model.eval()
        self.mcts = MCTS(self.model)

    def get_best_move(
        self,
        board: Board,
        color: int,  # 1=red, 2=black
        n_simulations: int = 800,
        temperature: float = 0.1,
    ) -> Move:
        """
        主推理接口
        返回最佳着法
        """
        from chess.piece import Color
        c = Color(color)

        result = self.mcts.search(board, c, n_simulations)

        if temperature < 0.01:
            return result.best_move

        # 带温度采样
        probs = result.action_probs ** (1.0 / temperature)
        probs /= probs.sum()
        idx = np.random.choice(len(probs), p=probs)
        return self.mcts.idx_to_move(idx)

    def get_policy_and_value(
        self,
        board: Board,
        color: int,
    ) -> tuple[np.ndarray, float]:
        """获取策略概率和价值评估（用于分析界面）"""
        from chess.piece import Color
        c = Color(color)

        features = encode_board_tensor(board.grid).to(self.device)
        with torch.no_grad():
            log_pi, v = self.model(features.unsqueeze(0))
            pi = torch.exp(log_pi).numpy()[0]
            value = float(v.item())

        return pi, value
```

---

## 九、训练配置

```python
# config.py
@dataclass
class TrainingConfig:
    # 数据
    MIN_BUFFER_SIZE: int = 5_000     # 开始训练的最小 buffer 大小
    BUFFER_CAPACITY: int = 100_000    # Replay Buffer 容量

    # 自对弈
    GAMES_PER_ITER: int = 100        # 每次迭代生成的对局数
    MCTS_SIMS_SELFPLAY: int = 400    # 自对弈时的 MCTS 模拟次数

    # 训练
    BATCH_SIZE: int = 256
    TRAINING_STEPS_PER_ITER: int = 100
    TOTAL_STEPS: int = 1_000_000

    # 优化器
    LR: float = 1e-3
    WEIGHT_DECAY: float = 1e-4
    WARMUP_STEPS: int = 4_000

    # 学习率调度
    SAVE_INTERVAL: int = 10_000        # 每 N 步保存 checkpoint
    EVAL_INTERVAL: int = 50_000       # 每 N 步评估模型

    # 评估
    EVAL_GAMES: int = 200             # 评估时的对局数
    BASELINE_ELO: float = 1800        # 旧模型 Elo 基准

    # 模型
    RES_BLOCKS: int = 19
    CHANNELS: int = 256
    MODEL_VERSION: str = "v0.1.0"
    CHECKPOINT_DIR: str = "./checkpoints"
```
