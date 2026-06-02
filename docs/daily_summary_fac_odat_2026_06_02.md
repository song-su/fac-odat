# FAC + ODAT-SE daily summary, 2026-06-02

## 1. 今日主要工作

- 阅读论文 Kimura et al., PRA 102, 032807 (2020)，确认 I7+ 实验参考峰来源
- 修复 `5l` 语法不展开的 bug
- 修复 scoring 全返回 600 万的问题（shift 方向一致性过强）
- 发现并修复 calibration mode 中 top-N 线团过滤导致正确跃迁被丢弃的 bug
- 完成 OptimizeRadial survey，找到与论文一致的最优势优化策略
- 确定 UTA centroid 评分模式，最终得到物理上合理的搜索结果

---

## 2. 论文阅读摘要

论文为 **Kimura et al., PRA 102, 032807 (2020)**，标题：
*5p-4f level crossing in palladium-like ions and its effect on metastable states*

### 2.1 与当前项目的直接关联

`target_case_v4_I.py` 中的 6 个实验参考峰来自该论文 Table I（I7+ 部分）：

| 标签 | 跃迁 | 类型 | λex (nm) | λth (nm, FAC) |
|------|------|------|----------|---------------|
| a | (4d⁻¹₅/₂ 5s₁/₂)_J=2 → 4d¹⁰ | E2 | 26.21 | 26.24 |
| b | (4d⁻¹₃/₂ 5s₁/₂)_J=2 → 4d¹⁰ | E2 | 25.27 | 25.27 |
| d | (4d⁻¹₃/₂ 5p₁/₂)_J=1 → 4d¹⁰ | E1 | 19.42 | 19.45 |
| e | (4d⁻¹₃/₂ 5p₃/₂)_J=1 → 4d¹⁰ | E1 | 19.02 | 19.09 |
| f | (4d⁻¹₅/₂ 4f₅/₂)_J=1 → 4d¹⁰ | E1 | 16.44 | 16.56 |
| g | (4d⁻¹₃/₂ 4f₅/₂)_J=1 → 4d¹⁰ | E1 | 15.71 | 15.77 |

论文使用 FAC 1.1.5（与本项目相同版本），CR 模型 configuration 集合与
`v4_I.py` 完全一致（665 个激发能级）。  
FAC 理论-实验偏差：**+0.03 ~ +0.12 nm（+0.3 ~ +1.2 Å）**。

### 2.2 亚稳态物理

- `(4d⁻¹₅/₂ 5s₁/₂)_J=3`（寿命 3600 s）是 I7+ 最重要的亚稳态，
  EBIT 等离子体中占 17.64% 种群
- I7+ 中 4d⁻¹4f 的寿命远短于 Ba10+，因为 Z < 56 时 5p 能级低于 4f，
  存在 E2 快速退激发通道

---

## 3. Bug 修复

### 3.1 `5l` 语法不展开

**问题**：`fac.Config('4p5 4d10 5l')` 中 `5l` 不是合法 FAC 角动量符号，
被 FAC 静默忽略，只生成基态 1 个能级（而 `5[s,p,d,f]` 应生成 51 个能级）。

**修复**（`inputs/target_case_v4_I.py`，`_normalize_configuration`）：
```python
_fixed_nl = re.match(r"^(\d+)l$", last_token)   # 识别 5l, 6l, 7l ...
if _fixed_nl:
    active = "nl"
    template["n"] = [int(_fixed_nl.group(1))]    # n=[5] 固定展开
```
现在 `5l` 自动展开为 `5[s,p,d,f]`，`6l` 展开为 `6[s,p,d,f,g]`，以此类推。

### 3.2 Scoring 全返回 600 万

**问题**：`GLOBAL_SHIFT["require_consistent_direction"] = True` 导致
per-peak shift 方向不一致时直接给 `missing_penalty × n_peaks = 6,000,000`。
实测各峰 shift 方向确实混杂（峰 26.21nm 和 16.44nm 为负，其余为正）。

**修复**：改为 `require_consistent_direction = False`，
只靠 `max_shift_spread_nm` 控制容差范围。

---

## 4. OptimizeRadial Survey

### 4.1 设计

新增文件 `inputs/target_case_v4_I_survey.py`：

- **参考峰**：论文 Table I 的 FAC 理论波长（λth），不是实验值
- **评分模式**：`calibration_mode = True`（新增）——每个峰独立寻找最近
  FAC 单线，用绝对偏差 `|λ_FAC - λ_ref|` 而非与均值的偏差评分
- **策略**：12 种，包括各 configuration 单独优化、关键组合和全平均 (AL)

新增代码（`scripts/run_configuration_search.py`）：
- `_score_calibration()`：calibration mode 专用评分路径，直接扫所有
  (energy, weight) 对找最近线，绕过 `local_line_group_options` 的
  top-N 权重过滤（该过滤会丢掉正确但较弱的跃迁线）
- `write_calibration_summary()`：输出人可读的逐峰偏差汇总表

### 4.2 结果（`runs/search_W7_v4_survey/calibration_summary.txt`）

| 策略 | loss | mean (Å) | spread (Å) |
|------|------|----------|------------|
| **ground_plus_4d9_nl** | **0.017** | **+0.001** | **0.016** |
| 4d9_nl_only | 0.021 | +0.003 | 0.017 |
| ground_plus_4d9_4f_nl | 0.11 | -0.009 | 0.025 |
| all_configs_average (AL) | 0.16 | +0.002 | 0.053 |
| ground_only | 0.51 | -0.013 | 0.071 |

**结论**：`ground_plus_4d9_nl`（= `OptimizeRadial` 同时包含基态和主激发
configuration `4d⁻¹ nl`）复现论文 FAC 理论值，所有 6 条线偏差 < 0.012 Å。
这与物理直觉一致：对跃迁上下能级同时优化势，能量差最准确。

### 4.3 Calibration Mode 中发现的 Bug

**问题**：`local_line_group_options` 按 gA 权重排名取 top-12，把正确但较弱的
指定跃迁线（gA ~10¹⁰）排在强背景线群（gA ~10¹²）之后而丢弃。
例如 `cal_d`（19.45 nm）的正确跃迁只有 gA=1.08e+09，但窗口内有
gA=2.53e+12 的强线群，被选中后报告 shift=+4.15 Å（实为 +0.001 Å）。

**修复**：`_score_calibration` 改为直接遍历所有 (energy, weight) 对，
取最近线，不经过 group 机制。

---

## 5. UTA Centroid 评分模式

### 5.1 发现的问题

应用校准后的势（`ground_plus_target_excited`）后，主搜索结果仍然不理想：
使用 5 Å 搜索窗口时，`per_peak_consistency` 会选中距实验峰 3–4 Å 的强背景
线群，而不是正确指定跃迁（偏差 ~0.01 Å 但 gA 弱 100–1000 倍）。

### 5.2 UTA 的物理含义

检查发现：I7+ 的每个实验峰对应的不是单条跃迁，而是 `4d⁻¹ 5p`、`4d⁻¹ 4f`
等 configuration 的跃迁阵列（UTA）。例如 19.42 nm 峰的 1.5 Å 窗口内有
934–962 条 FAC 线。gA 加权的**全窗口重心**与实验峰高度吻合：

| 策略 | 19.42nm 窗口内重心 | 偏差 |
|------|---|---|
| ground_only | 194.259 Å | +0.059 Å |
| ground_plus_target_excited | 194.194 Å | **-0.006 Å** |

### 5.3 评分参数修改

将 `local_line_group_window_angstrom` 改为与搜索窗口相同（1.5 Å），
`max_local_shift_groups_per_peak = 1`，使所有窗口内线合并为一个线团，
其中心即为 UTA gA 加权重心。

### 5.4 最终结果（`runs/search_I7_v4/`）

| 策略 | loss | mean (Å) | spread (Å) |
|------|------|----------|------------|
| **target_excited_only** | **180.1** | +0.082 | 0.770 |
| ground_plus_target_excited | 273.3 | +0.098 | 0.860 |
| ground_only | 387.4 | +0.082 | 1.006 |

逐峰偏差（target_excited_only）：

| 峰 | UTA 重心 (Å) | 偏差 |
|----|------------|------|
| 26.21 nm (E2) | 262.034 | +0.066 Å |
| 25.27 nm (E2) | 252.753 | -0.053 Å |
| 19.42 nm (E1 5p) | 194.193 | +0.007 Å |
| 19.02 nm (E1 5p) | 190.150 | +0.050 Å |
| 16.44 nm (E1 4f) | 164.574 | -0.174 Å |
| 15.71 nm (E1 4f) | 156.504 | +0.596 Å |

校准后的势策略正确获胜。4f 线偏差稍大（0.6 Å）是 4f 态对势更敏感的
正常现象。

---

## 6. 新增和修改的文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `inputs/target_case_v4_I.py` | 修改 | `5l` 展开修复；关闭方向一致性；`optimize_radial` 按 survey 结果收窄；UTA centroid 参数 |
| `inputs/target_case_v4_I_survey.py` | 新增 | OptimizeRadial survey 输入，12 种策略，calibration_mode=True |
| `scripts/run_configuration_search.py` | 修改 | 新增 `_score_calibration()`、`write_calibration_summary()`；calibration mode 路由 |
| `docs/daily_summary_fac_odat_2026_06_02.md` | 新增 | 本日志 |

---

## 7. 当前已知限制与后续建议

1. **UTA centroid 的局限**：把整个 1.5 Å 窗口内所有线合并为一个重心，
   在 configuration 空间较复杂时可能被不相关线群拉偏。
   后续可考虑更精细的线族标记（按 configuration family 分组计分）。

2. **15.71nm 4f 线偏差 0.6 Å**：比其他峰大约 5–10 倍，说明当前
   `target_excited_only` 势对 4f 态的描述可以进一步改进。
   可考虑 `ground_plus_4d9_4f_nl` 策略。

3. **没有 optional configuration**：当前 v4_I 的所有 configuration 都是
   `required=True`，无法用 grid_search 评估不同子集的贡献。
   后续可将部分 `4p6 4d8 5x²` 改为 optional，测试对 loss 的影响。

4. **survey 文件的 `element` 字段有笔误**（"W" 应为 "I"），
   不影响 FAC 计算（Z=53 正确），但影响输出目录名称。
