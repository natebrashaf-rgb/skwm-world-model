# 🌍 自主建立世界模型 —— 完整教程

> 基于论文 **《World-in-World: World Models in a Closed-Loop World》**（arXiv:2510.18135）
> 参照模版 **《科学知识世界模型驱动的高校图书馆智能学科服务模式研究》**

---

## 📖 教程目录

1. [什么是世界模型？](#1-什么是世界模型)
2. [World-in-World 核心思想（大白话版）](#2-world-in-world-核心思想大白话版)
3. [核心算法拆解](#3-核心算法拆解)
4. [步骤一：搭建环境](#4-步骤一搭建环境)
5. [步骤二：理解"闭循环"（Closed-Loop）](#5-步骤二理解闭循环closed-loop)
6. [步骤三：统一动作 API](#6-步骤三统一动作-api)
7. [步骤四：提案-模拟-修正 循环](#7-步骤四提案-模拟-修正-循环)
8. [步骤五：后训练（Post-Training）](#8-步骤五后训练post-training)
9. [步骤六：完整可运行的迷你实现](#9-步骤六完整可运行的迷你实现)
10. [如何迁移到你的高校图书馆场景？](#10-如何迁移到你的高校图书馆场景)

---

## 1. 什么是世界模型？

**世界模型 = 让AI能"想象未来"的模型。**

就像你闭上眼睛能想象"如果我往前走一步，会看到什么"，世界模型就是给AI这种"预演"能力。

### 世界模型的三件大事：

| 能力 | 比喻 | 代码层面的意思 |
|------|------|----------------|
| **感知** | 看到当前环境 | 输入一张图片/一个状态 |
| **预测** | 想象如果做了某个动作会怎样 | 输入(当前状态+动作)，输出(未来状态) |
| **规划** | 选择最好的动作序列 | 用预测结果来比较不同动作的好坏 |

---

## 2. World-in-World 核心思想（大白话版）

> **"不要只看画面好不好看，要看世界模型能不能帮AI完成任务。"**

### 论文的三个惊人发现：

| 发现 | 大白话 | 对你的意义 |
|------|--------|-----------|
| **① 画面好≠任务成功** | 一个画得精美的世界模型可能帮AI做出错误决策 | 不要只看视觉效果，要看能不能用 |
| **② 后训练比换大模型更有效** | 拿少量"动作-观察"数据微调，比换一个更大的视频生成模型有用 | 小数据也能出好效果 |
| **③ 推理时多想想** | 让世界模型多模拟几次未来，决策质量大幅提升 | 多花点计算时间换更好的决策 |

### 核心架构（三段式循环）：

```
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ 提案策略  │ ──→  │ 世界模型  │ ──→  │ 修正策略  │
    │ π_proposal│      │    g_θ   │      │π_revision│
    └──────────┘      └──────────┘      └──────────┘
         ↑                                  │
         │          ┌──────────┐            │
         └──────────│ 真实环境  │ ←──────────┘
                    └──────────┘
```

**运作流程：**
1. **提案**：AI 提出 M 个候选动作计划
2. **模拟**：世界模型对每个计划预测未来结果
3. **修正**：评估所有模拟结果，选最好的执行
4. **循环**：执行后在真实环境中获取新状态，回到步骤1

---

## 3. 核心算法拆解

### 3.1 数学公式（别怕，都有白话翻译）

#### 公式1：提案策略
```
Â_t^(m) ~ π_proposal(A | o_t, g),  m = 1, ..., M
```
**白话**：AI 看到当前画面 o_t 和目标 g，想出了 M 种不同的动作计划。

#### 公式2：世界模型模拟
```
Ô_t^(m) ~ g_θ(O | o_t, I_t^(m))
Ô_t^(m) = [ô_t+1, ô_t+2, ..., ô_t+L]
```
**白话**：对每个候选计划，世界模型"想象"未来 L 步会看到什么。

#### 公式3：修正策略（选最优）
```
m* = arg max S(Â_t^(m), Ô_t^(m) | o_t, g)
D_t* = Â_t^(m*)
```
**白话**：比较所有模拟结果，选评分最高的那个执行。

### 3.2 统一动作 API（三类控制方式）

| 控制方式 | 世界模型类型 | 例子 |
|---------|-------------|------|
| **文本提示** | 文生视频模型 | "相机向前移动0.2米" |
| **相机轨迹** | 视图生成模型 | 设定 (x, y, 角度) 序列 |
| **底层动作** | 动作条件模型 | 直接输入离散动作 ID |

---

## 4. 步骤一：搭建环境

```bash
# 创建项目目录
mkdir -p ~/world_model_tutorial
cd ~/world_model_tutorial

# 安装依赖
pip install torch numpy matplotlib pillow
```

---

## 5. 步骤二：理解"闭循环"（Closed-Loop）

**闭循环 vs 开循环**：
- **开循环**：让模型生成一段视频，然后人类打分"好看不好看"
- **闭循环**：让模型生成视频后，AI 根据视频做决策，做对了才算好

> 这就像考试：开循环是"你猜答案"，闭循环是"你猜完答案还要解释为什么"。

---

## 6. 步骤三：统一动作 API

我已经为你准备了完整的代码。来看核心实现：

```python
# 动作 ID 映射
ACTION_IDS = {
    'forward': 1,    # 前进
    'turn_left': 2,  # 左转
    'turn_right': 3, # 右转
    'stop': 4,       # 停止
}

# 动作转为文本提示（给文生视频模型用）
def actions_to_text(actions):
    """把动作序列翻译成文字"""
    template = "Follow this sequence of camera motions: {action}."
    action_strings = []
    for a in actions:
        if a == 'forward':
            action_strings.append("forward 0.2m")
        elif 'turn' in a:
            action_strings.append(f"{a} 22.5°")
    return template.format(action=str(action_strings))

# 动作转为相机轨迹（给视图生成模型用）
def actions_to_trajectory(actions, start_pos=(0,0), start_angle=0):
    """把动作序列翻译成相机轨迹点"""
    trajectory = [(start_pos[0], start_pos[1], start_angle)]
    x, y, angle = start_pos[0], start_pos[1], start_angle
    for a in actions:
        if a == 'forward':
            x += 0.2 * np.cos(np.radians(angle))
            y += 0.2 * np.sin(np.radians(angle))
        elif a == 'turn_left':
            angle += 22.5
        elif a == 'turn_right':
            angle -= 22.5
        trajectory.append((x, y, angle))
    return trajectory
```

---

## 7. 步骤四：提案-模拟-修正 循环

这是最关键的算法。让我用一个**极简网格世界**来演示，这样你不用 GPU 也能运行。

### 场景：2D 网格世界

```
  0  1  2  3  4  5
0 [ ][ ][ ][ ][ ][ ]
1 [ ][ ][★][ ][ ][ ]    ★ = 目标
2 [ ][ ][ ][ ][ ][ ]    🤖 = 智能体
3 [ ][ ][ ][ ][ ][ ]
4 [🤖][ ][ ][ ][ ][ ]
5 [ ][ ][ ][ ][ ][ ]
```

**智能体**需要导航到 **目标**。每次可选动作：上、下、左、右。

### 完整算法流程

```python
def closed_loop_planning(agent, world_model, env, goal, M=5, horizon=3):
    """
    闭循环在线规划算法
    
    参数：
        agent: 提案策略 π_proposal
        world_model: 世界模型 g_θ（用来模拟未来）
        env: 真实环境
        goal: 目标
        M: 候选计划数
        horizon: 规划视野（向前看几步）
    """
    obs = env.get_observation()  # 当前观察
    
    for step in range(max_steps):
        # ====== 第一步：提案 ======
        # 生成 M 个候选动作序列
        candidates = []
        for m in range(M):
            plan = agent.propose_plan(obs, goal, horizon)
            candidates.append(plan)
        
        # ====== 第二步：模拟 ======
        # 对每个候选计划，用世界模型模拟未来
        simulated_futures = []
        for plan in candidates:
            future_states = world_model.simulate(obs, plan)
            simulated_futures.append((plan, future_states))
        
        # ====== 第三步：修正（评分并选择最优） ======
        best_score = -float('inf')
        best_plan = None
        for plan, future in simulated_futures:
            score = evaluate_plan(future, goal)
            if score > best_score:
                best_score = score
                best_plan = plan
        
        # ====== 执行第一步动作 ======
        action = best_plan[0]
        obs = env.step(action)
        
        # 检查是否到达目标
        if env.is_goal_reached(goal):
            break
    
    return env.trajectory
```

---

## 8. 步骤五：后训练（Post-Training）

后训练是 World-in-World 论文中最实用的技巧：

> **用少量"动作-观察"数据微调现有的视频生成模型**

### 为什么要后训练？
- 现成的视频生成模型（如 Stable Video Diffusion）是在互联网视频上训练的
- 它们不知道"前进0.2米"对应的像素变化是什么
- 用几百到几万条"动作→画面变化"数据微调，就能让它变成可用的世界模型

### 后训练数据长什么样？

```
┌─────────────────────────────────────────────┐
│ 动作: forward 0.2m                          │
│ 观察前: [RGB图片A]  →  观察后: [RGB图片B]  │
├─────────────────────────────────────────────┤
│ 动作: turn_left 22.5°                       │
│ 观察前: [RGB图片C]  →  观察后: [RGB图片D]  │
└─────────────────────────────────────────────┘
```

### 数据缩放定律（论文发现）：
- **数据越多，效果越好**（40K 到 80K 样本持续提升）
- **大模型吸收数据能力更强**（14B 比 1.5B 提升更明显）

---

## 9. 步骤六：完整可运行的迷你实现

下面是一个**完整、可运行**的极简版 World-in-World 实现。它在一个 2D 网格世界（而不是 3D 环境）中演示了完整的闭循环规划算法。

### 安装和运行

```bash
cd ~/world_model_tutorial
python simplified_world_in_world.py
```

### 输出示例

```
=== 第 1 步 ===
当前状态: (4, 0)
── 提案阶段：生成 5 个候选计划 ──
  计划 0: ['right', 'right', 'right']
  计划 1: ['right', 'up', 'right']
  计划 2: ['up', 'right', 'right']
  计划 3: ['right', 'right', 'up']
  计划 4: ['up', 'up', 'right']
── 模拟阶段：对每个计划预测未来 ──
  计划 0 模拟结果: [(4,1), (4,2), (4,3)]
  计划 1 模拟结果: [(4,1), (3,1), (3,2)]
  ...
── 修正阶段：评分并选择最优 ──
  计划 0 评分: 3.0
  计划 1 评分: 2.0
  计划 2 评分: 2.0
  ...
  最优计划: ['right', 'right', 'right']
  执行动作: right
  新状态: (4, 1)
```

---

## 10. 如何迁移到你的高校图书馆场景？

根据你的参照模版论文，世界模型的概念可以迁移到**科学知识世界模型（Scientific Knowledge World Model, SKWM）**：

| World-in-World 概念 | 你的 SKWM 概念 |
|-------------------|----------------|
| 智能体（Agent） | 学科馆员 / 研究生 |
| 环境（Environment） | 学术知识世界 |
| 观察（Observation） | 文献摘要 / 关键词 |
| 动作（Action） | 检索 / 分析 / 推荐 |
| 世界模型（World Model） | 科学知识图谱 + 向量数据库 |
| 模拟未来（Simulate） | GraphRAG 多跳推理 |
| 任务成功（Task Success） | 回答准确率 / 文献覆盖率 |

### 具体迁移步骤：

1. **数据层**：用中阿文旅文献、政策、项目数据构建知识图谱
2. **知识组织**：定义实体（作者、机构、主题）和关系（引用、合作、共现）
3. **世界模型**：用 Embedding + 知识图谱 + GraphRAG 作为"预测器"
4. **闭循环**：用户提问 → 知识世界模型预测 → 检索验证 → 馆员审核 → 反馈回写

这正好对应你的参照论文中的 **"资源采集—知识组织—状态感知—智能服务—馆员审核—知识沉淀"** 闭环！

---

## 下一步

运行 `simplified_world_in_world.py` 开始你的第一个世界模型实验吧！
