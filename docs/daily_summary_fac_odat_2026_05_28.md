# FAC + ODAT-SE daily summary, 2026-05-28

## 1. 今日主要工作

今天继续修改 phase-1 loss 设计，重点解决：

- FAC-only 阶段不能只取最大 gA 线；
- 权重应允许在输入文件中选择 `A` 或 `(2J+1)*A`；
- 初筛阶段不应强制所有峰共享完全相同的 global shift；
- 但不同实验峰所需的 wavelength shift 应方向一致、幅度接近。

## 2. A / gA 权重可配置

修改文件：

```text
scripts/run_configuration_search.py
inputs/target_case_v4.py
```

原先 `.tr` 读取后固定使用：

```text
weight = (upper_2J + 1) * A
```

今天改为由输入文件控制：

```python
"radiative_weight": "(2J+1)*A"
```

也可以改为：

```python
"radiative_weight": "A"
```

原因是当前阶段没有 CRM population，真实强度应为：

```text
I_ul ∝ N_u A_ul
```

因此 `A` 或 `gA` 都只能作为 radiative-potential proxy，不能直接等同于真实谱线强度。

弱线过滤仍通过：

```python
"min_A_value": None
```

控制。若设置为：

```python
"min_A_value": 1e9
```

则 `A < 1e9 s^-1` 的线在解析 `.tr` 时直接丢弃，不参与后续 loss。

## 3. 新增 per-peak shift consistency 模式

之前 v4 使用一个统一 global shift。今天确认初筛阶段更合适的条件不是：

```text
所有峰必须使用同一个 shift
```

而是：

```text
每个峰可以有自己的 shift；
这些 shift 不必完全相同；
但方向应一致，且相互差值应在容差内。
```

因此在 `inputs/target_case_v4.py` 中将 shift 模式改为：

```python
GLOBAL_SHIFT = {
    "enabled": True,
    "mode": "per_peak_consistency",
    "require_consistent_direction": True,
    "direction_zero_tolerance_angstrom": 1.0e-6,
    "max_shift_spread_angstrom": 0.5,
    "max_abs_shift_angstrom": None,
}
```

其中：

```text
shift_p = lambda_exp,p - lambda_center,p
```

接受条件为：

```text
所有 shift_p 方向一致
max(shift_p) - min(shift_p) <= 0.5 A
```

例如：

```text
peak A shift = +3.0 A
peak B shift = +2.6 A
spread = 0.4 A
```

该情况通过初筛，因为两个峰所需 shift 同向且差值小于 `0.5 A`。

`max_abs_shift_angstrom = None` 表示当前不限制 shift 的绝对大小，只限制不同峰之间的相对一致性。如果未来需要限制绝对偏移，可以设置例如：

```python
"max_abs_shift_angstrom": 5.0
```

## 4. 新 loss 形式

在 `mode = "per_peak_consistency"` 下，每个峰先寻找候选理论线团，再计算：

```text
lambda_center,p = Σ_i lambda_i weight_i / Σ_i weight_i
shift_p = lambda_exp,p - lambda_center,p
score_p = Σ_i weight_i
```

其中 `weight_i` 由输入文件的 `radiative_weight` 决定，可以是：

```text
A
(2J+1)*A
```

若 shift consistency 通过，当前 loss 为：

```text
L = Σ_p [
      position_weight * peak_weight * (shift_p - mean_shift)^2
      - strength_weight * peak_weight * log(score_p + rate_floor)
    ]
    + complexity_penalty
```

其中：

```text
mean_shift = average(shift_p)
```

因此位置项不再惩罚共同的大 shift，而是惩罚不同峰之间 shift 的不一致。

如果存在以下情况：

```text
某个峰找不到候选线团
shift 方向不一致
shift spread 超过 max_shift_spread_angstrom
```

则该 trial 直接给：

```text
loss = missing_peak_penalty * number_of_peaks
```

## 5. 局部线团参数

今天新增两个参数：

```python
"local_line_group_window_angstrom": 0.1,
"max_local_shift_groups_per_peak": 12,
```

它们只在：

```python
GLOBAL_SHIFT["mode"] = "per_peak_consistency"
```

下使用。

### local_line_group_window_angstrom

`local_shift_search_window_angstrom` 是大搜索窗口，例如：

```python
"local_shift_search_window_angstrom": 5.0
```

表示每个实验峰先在 `±5 A` 范围内寻找理论线。

但不能把这个大窗口中的所有线全部平均，否则不同候选线团会互相污染。因此新增：

```python
"local_line_group_window_angstrom": 0.1
```

表示在大窗口内，把彼此靠近的理论线聚成局部线团。线团内部再用 `A` 或 `gA` 加权平均。

### max_local_shift_groups_per_peak

一个实验峰的 `±5 A` 范围内可能存在很多局部线团。如果每个峰都保留所有线团，跨峰组合数会快速爆炸。

因此新增：

```python
"max_local_shift_groups_per_peak": 12
```

表示每个实验峰只保留总权重最大的前 12 个局部线团，进入后续 shift consistency 组合匹配。

## 6. 当前实现流程

当前 per-peak shift scoring 流程为：

```text
1. 读取 FAC .tr 文件；
2. 按 min_A_value 丢弃弱线；
3. 根据 radiative_weight 选择 A 或 (2J+1)*A；
4. 对每个实验峰，在 local_shift_search_window_angstrom 内找理论线；
5. 用 local_line_group_window_angstrom 聚成局部线团；
6. 每个峰保留最强的 max_local_shift_groups_per_peak 个线团；
7. 跨峰选择一组线团，使 shift 方向一致且 spread <= 0.5 A；
8. 若通过，计算 loss；
9. 若不通过，给 missing penalty。
```

输出的 `peak_summary` 中新增或保留了以下字段：

```text
local_shift
mean_shift
shift_spread
shift_out_of_range
shift_failure_reason
radiative_weight
```

其中 `shift_failure_reason` 可能为：

```text
missing_peak
shift_consistency
```

## 7. 验证

今天完成了语法检查：

```bash
python3 -m py_compile scripts/run_configuration_search.py inputs/target_case_v4.py
```

检查通过。

还用合成数据验证了：

```text
shift = +3.0 A, +2.9 A, +2.8 A, +2.7 A, +2.6 A
```

这类同向且 spread 小于 `0.5 A` 的情况可以通过。

明显不一致的 shift 组合会被标记为：

```text
shift_consistency
```

没有重新运行完整 FAC grid search。

## 8. 新增 v5：从目标激发态尝试 OptimizeRadial

今天继续讨论 radial potential 的起点问题。

之前 `OPTIMIZE_RADIAL = "auto"` 的默认行为是：

```text
OPTIMIZE_RADIAL_BASE = "first_required"
```

因此所有自动生成的 `OptimizeRadial` 策略都会包含第一组 required
configuration。当前 W46 输入中第一组 required 是基态：

```text
3p6_3d10
```

也就是说，v4 的势优化策略默认都是 ground-based potential，例如：

```text
base_only                 -> 3p6_3d10
base_plus_3p6_3d9_nl      -> 3p6_3d10 + 3p6_3d9_nl
base_plus_3p5_3d10_nl     -> 3p6_3d10 + 3p5_3d10_nl
```

今天确认：FAC 本身并不要求 `OptimizeRadial` 必须包含基态组。
这只是当前输入文件中的搜索策略选择。

因此新增了一个独立输入文件：

```text
inputs/target_case_v5.py
```

v5 继承 v4 的设置：

```text
wavelength-space scoring
per_peak_consistency shift mode
local line group matching
A / (2J+1)*A radiative weight switch
```

但只改变 radial potential 搜索策略。

### 物理动机

如果目标实验峰主要来自某类激发 configuration，基态优化出来的中心势未必是
描述这些跃迁能量最优的势。可以先比较：

```text
ground-based potential
target-excited-state-based potential
```

再看它们分别和其他 configuration 配合后的 loss。

这在 phase-1 初筛中是合理的，因为当前目标不是最终 CRM 真实强度拟合，而是判断
某组 configuration / potential 是否能在实验峰附近产生合理线团。

### v5 当前目标激发态

当前 v5 中设置：

```python
TARGET_EXCITED_CONFIGURATION = "3p6_3d9_nl"
```

即把 `3p6 3d9 nl` 作为目标激发态势优化起点。

### v5 显式 OptimizeRadial 策略

v5 不再使用 v4 的 `auto` 策略，而是显式生成：

```text
ground_only
target_excited_only
ground_plus_target_excited
ground_plus_3p5_3d10_nl
target_excited_plus_3p5_3d10_nl
ground_plus_3p6_3d8_4s2
target_excited_plus_3p6_3d8_4s2
ground_plus_3p5_3d9_4s2
target_excited_plus_3p5_3d9_4s2
```

其中 selected configuration set 仍然由 required / optional 枚举决定；
`OptimizeRadial` 只在当前 trial 已选中的 configuration 之间选择合法组合。

### v5 输出路径

v5 自动输出到：

```text
runs/search_W46_v5
generated/search_W46_v5
runs/search_W46_v5/results.txt
```

### 验证

已完成语法检查：

```bash
python3 -m py_compile inputs/target_case_v5.py
```

并检查配置加载和 trial 枚举：

```text
n_strategies = 9
n_trials = 28
```

没有实际运行 FAC。运行命令为：

```bash
python3 scripts/run_configuration_search.py inputs/target_case_v5.py --clean
```

## 9. v4 / v5 合并：configuration 级别标注 potential 用途

随后确认：不应把 v5 做成一套独立外挂逻辑，而应把“是否进入 FAC 计算”和
“是否参与 `OptimizeRadial`”都放回 configuration 输入层标注。

之前 configuration 只主要表达：

```python
{"config": "3p6 3d10", "required": True}
```

其中：

```text
required=True  -> 每个 FAC calculation trial 都包含该 configuration
required=False -> 作为 optional configuration，由 grid search 做 on/off 枚举
```

现在新增 potential 相关标注：

```python
{
    "config": "3p6 3d10",
    "required": True,
    "optimize_radial": True,
    "optimize_radial_base": True,
    "potential_label": "ground",
}
```

含义为：

```text
required
  控制该 configuration 是否进入 FAC calculation set。

optimize_radial
  控制该 configuration 是否允许出现在 OptimizeRadial groups 中。

optimize_radial_base
  控制该 configuration 是否作为 potential 起点单独比较。

potential_label
  只用于生成可读的 strategy id，例如 ground_only。
```

当前 `inputs/target_case_v4.py` 中将两个 configuration 标成 potential base：

```text
3p6_3d10      -> potential_label = ground
3p6_3d9_nl    -> potential_label = target_excited
```

因此 v4 的 `OPTIMIZE_RADIAL = "auto"` 已经合并了原 v5 的能力，会自动生成：

```text
ground_only
ground_plus_target_excited
ground_plus_3p5_3d10_nl
ground_plus_3p6_3d8_4s2
ground_plus_3p5_3d9_4s2
target_excited_only
target_excited_plus_3p5_3d10_nl
target_excited_plus_3p6_3d8_4s2
target_excited_plus_3p5_3d9_4s2
```

`ground_plus_target_excited` 和 `target_excited_plus_ground` 物理上是同一个
`OptimizeRadial` group set，因此自动生成时按无序 group set 去重，只保留一个。

`inputs/target_case_v5.py` 现在改为兼容入口，不再维护独立策略。它复用 v4 的
合并逻辑，只把输出版本号保持为：

```text
v5
```

所以：

```text
inputs/target_case_v4.py -> runs/search_W46_v4
inputs/target_case_v5.py -> runs/search_W46_v5
```

两者使用同一套 configuration-level potential 标注逻辑。

### 验证

已完成语法检查：

```bash
python3 -m py_compile inputs/target_case_v4.py inputs/target_case_v5.py scripts/generate_fac_input.py scripts/run_configuration_search.py
```

配置枚举检查：

```text
v4 strategies = 9
v4 trials     = 28
v5 strategies = 9
v5 trials     = 28
```

并检查 `target_excited_only` 的 FAC 输入生成结果：

```python
fac.OptimizeRadial(['n3', 'n4', 'n5', 'n6'])
```

这说明目标激发态 `3p6 3d9 nl` 已经正确映射为展开后的 FAC group，而不是基态组。

没有实际运行完整 FAC grid search。
