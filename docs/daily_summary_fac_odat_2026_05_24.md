# FAC + ODAT-SE 2026-05-24 记录

## 1. 今日主要目标

今天围绕 `inputs/target_case_v2.yaml` 做了 v2 搜索输入和脚本适配。

重点目标是：

- 使用 v2 输入文件；
- 修正实验参考波长单位；
- 加入额外 configuration；
- 不再做完整指数级 configuration 子集搜索；
- 改成基于 loss 的逐层 forward selection；
- 实际跑一次 FAC 搜索并检查结果。

## 2. 实验峰单位修正

原先 v2 输入中实验峰写成：

```yaml
wavelength:
  value: 5.69
  unit: "nm"
```

今天确认这是错误单位。当前实验波长单位应为埃：

```yaml
wavelength:
  value: 5.69
  unit: "angstrom"
```

对应当前两个参考峰：

```text
5.69 A -> 2178.98415524 eV
5.87 A -> 2112.16692390 eV
```

输入文件中峰 id 也改为：

```text
peak_5p69A
peak_5p87A
```

## 3. Configuration 空间

原 v2 中的参考 configuration 仍保留：

```text
ground_3p6_3d10      -> 3p6 3d10
hole_3d9_nl          -> 3p6 3d9 nl, n = 4,5,6; l = 0,1,2,3,4
hole_3p5_3d10_nl     -> 3p5 3d10 nl, n = 4,5,6; l = 0,1,2,3,4
```

今天额外加入两个 optional configuration：

```text
hole_3d8_4s2         -> 3p6 3d8 4s2
hole_3p5_3d9_4s2     -> 3p5 3d9 4s2
```

这些新增项用于测试搜索逻辑是否会因为“多加 configuration”而继续扩大模型。

## 4. OptimizeRadial 搜索策略

v2 中 `OptimizeRadial` 作为搜索变量。

今天新增了两个对应策略：

```text
ground_plus_3d8_4s2
  groups = ["ground_3p6_3d10", "hole_3d8_4s2"]

ground_plus_3p5_3d9_4s2
  groups = ["ground_3p6_3d10", "hole_3p5_3d9_4s2"]
```

原有策略继续保留：

```text
ground_only
ground_plus_3d_hole
ground_plus_3p_hole
```

## 5. v2 脚本适配

修改了：

```text
scripts/generate_fac_input.py
scripts/run_configuration_search.py
```

### generate_fac_input.py

修正点：

- v2 YAML 不再必须提供 `configuration_space.manual_fac_configs`；
- 当 trial 中注入 `radial_potential.optimize_radial_groups` 时，生成器使用该组；
- 若没有注入，则从 `optimize_radial_strategies` 取第一个策略作为 fallback。

### run_configuration_search.py

修正点：

- 支持 v2 的 `optimize_radial_strategies`；
- 支持 Gaussian soft window；
- 支持 `(2J+1)*A` radiative weight；
- 支持 global energy shift；
- 支持 anchor / ambiguous peak 权重；
- 支持 complexity penalty；
- 输出结果 CSV 中加入：

```text
round
candidate_template_id
accepted
```

此外，真实运行时发现 `peak_energies()` 没有把 `fwhm_eV / sigma_eV / type`
从 YAML peak 传给 loss 计算，导致 v2 scoring 报错。今天已修正。

## 6. 搜索策略改变

一开始讨论过“如果出现已知正确 configuration 就立刻停止”，并临时实现过
`stop_on_configuration`。

随后确认更合理的是继续使用 loss 排名，但不能做完整全组合暴力枚举。

因此当前 v2 使用：

```yaml
search:
  method: "greedy_forward_selection"
  stop_on_configuration:
    enabled: false
  forward_selection:
    min_loss_improvement: 0.0
    max_rounds: null
```

当前逻辑：

1. 先运行 required baseline；
2. 每轮测试 `current best + one remaining optional template`；
3. 对每个 candidate 同时测试可用的 `OptimizeRadial` 策略；
4. 接受 loss 最低且比当前 best 更低的 candidate；
5. 若本轮没有任何 candidate 降低 loss，则停止。

这样仍基于 loss 排名，但避免完整指数级组合搜索。

## 7. 今日实际 FAC 搜索结果

运行命令：

```bash
python3 scripts/run_configuration_search.py inputs/target_case_v2.yaml --clean
```

结果文件：

```text
runs/search_W46_v2/results.csv
```

搜索过程：

```text
baseline: ground_3p6_3d10
round 1: accepted hole_3d9_nl
round 2: tried adding hole_3p5_3d10_nl, hole_3d8_4s2, hole_3p5_3d9_4s2
round 2: no candidate improved the current best loss, so stopped
```

当前 best：

```text
trial_id: trial_0003
selected_template_ids: ground_3p6_3d10;hole_3d9_nl
optimize_radial_strategy_id: ground_plus_3d_hole
loss: -69.3928807497997
```

对应峰团摘要：

```text
peak_5p69A:
  n_lines = 1
  center_eV = 2183.086
  residual_eV = -0.9843843319131338
  energy_shift_eV = -3.1174604273091973

peak_5p87A:
  n_lines = 2
  center_eV = 2114.3
  residual_eV = 0.9843843319131338
  energy_shift_eV = -3.1174604273091973
```

用户认为正确的完整组合也已经被跑到：

```text
ground_3p6_3d10;hole_3d9_nl;hole_3p5_3d10_nl
```

但当前 loss 下未胜出：

```text
trial_0011:
  selected_template_ids = ground_3p6_3d10;hole_3d9_nl;hole_3p5_3d10_nl
  optimize_radial_strategy_id = ground_plus_3d_hole
  loss = -67.50110508797655
```

由于 loss 越小越好，当前程序选择 `ground + hole_3d9_nl`，而不是完整正确组合。

## 8. 当前重要判断

今天的结果说明：

```text
搜索逻辑已经能跑到正确组合；
问题在于当前 loss 设计偏向更小模型。
```

可能原因：

- `complexity.per_optional_template = 2.0` 对第二个 optional configuration 惩罚偏强；
- 新增 configuration 带来的额外线团没有通过 strength/log score 得到足够奖励；
- 当前 phase-1 loss 仍只看 FAC radiative potential，不含 CRM population，因此某些物理正确项可能不被 FAC-only loss 奖励。

下一步应重点检查：

```text
loss.complexity.per_optional_template
loss.strength_weight
peak type / anchor vs ambiguous 权重
prefilter_window_eV 和 fwhm_eV
```

必要时可以先降低或关闭 complexity penalty，验证正确组合是否能在 loss 排名中上升。

## 9. 后续输入扩展

今天后续继续扩展了 `inputs/target_case_v2.yaml`。

### 新增实验峰

在原有两个参考峰基础上加入三个实验波峰：

```text
peak_7p0262A = 7.0262 angstrom -> 1764.59819580 eV
peak_7p1733A = 7.1733 angstrom -> 1728.41228491 eV
peak_7p9280A = 7.9280 angstrom -> 1563.87737681 eV
```

当前五个峰全部暂用：

```text
fwhm_eV: 3.0
sigma_eV: null
type: anchor
```

### nl 空间修正

后续确认 `nl` 空间不应停在：

```text
n = 4,5,6
l = 0,1,2,3,4
```

而应扩展为：

```text
n = 4,5,6,7
l = 0,1,2,3,4,5,6
```

已对两个模板同时修正：

```text
hole_3d9_nl
hole_3p5_3d10_nl
```

生成的 FAC input 中确认包含：

```text
3p6 3d9 7[s,p,d,f,g,h,i]
3p5 3d10 7[s,p,d,f,g,h,i]
```

## 10. 搜索输出改进

按用户要求，修改了 `scripts/run_configuration_search.py`：

1. 每个 trial 输出目录中保留对应 FAC 输入脚本；
2. 额外生成一个简表：

```text
runs/search_W46_v2/loss_configuration_optimization.csv
```

该表包含：

```text
loss
configuration
optimization
trial_id
```

排序方式已改为：

```text
loss 升序排列
```

即 loss 最小、当前最优的 trial 在第一行。

## 11. 扩展后重新运行结果

使用扩展后的五个实验峰和 `n=4..7, l=0..6` 后重新运行：

```bash
python3 scripts/run_configuration_search.py inputs/target_case_v2.yaml --clean
```

新结果文件：

```text
runs/search_W46_v2/results.csv
runs/search_W46_v2/loss_configuration_optimization.csv
```

这次 greedy forward selection 的关键过程：

```text
round 1: accepted hole_3d9_nl
round 2: accepted hole_3p5_3d10_nl
round 3: tried adding hole_3d8_4s2 / hole_3p5_3d9_4s2
round 3: no candidate improved current best, so stopped
```

当前 best 已变为用户认为正确的完整组合：

```text
trial_id: trial_0012
selected_template_ids: ground_3p6_3d10;hole_3d9_nl;hole_3p5_3d10_nl
optimize_radial_strategy_id: ground_plus_3p_hole
loss: -162.10704999650113
```

扩展后搜索共运行：

```text
26 trials
```

并确认每个 trial 目录中都有对应输入脚本，例如：

```text
runs/search_W46_v2/trial_0012/trial_0012.py
```

## 12. OptimizeRadial 变化位置

搜索执行顺序中，第一次改变 optimization potential 是：

```text
trial_0003
selected_template_ids = ground_3p6_3d10;hole_3d9_nl
optimize_radial_strategy_id = ground_plus_3d_hole
FAC OptimizeRadial = ['n2', 'n3', 'n4', 'n5', 'n6']
```

其中：

```text
n2    = ground_3p6_3d10
n3-n6 = hole_3d9_nl, n = 4..7
```

当前 best `trial_0012` 的 FAC input 中：

```text
fac.OptimizeRadial(['n2', 'n7', 'n8', 'n9', 'n10'])
```

对应：

```text
n2     = ground_3p6_3d10
n7-n10 = hole_3p5_3d10_nl, n = 4..7
```

也就是说当前 best 的 radial potential 是用：

```text
ground + hole_3p5_3d10_nl
```

优化的，不包含 `hole_3d9_nl` 那组进入 `OptimizeRadial`。

## 13. 当前 loss 定义

当前 v2 loss 使用 Gaussian soft window。

每个实验峰先从波长转能量：

```text
E_exp = hc / wavelength_angstrom
```

对每条 FAC 理论线，若：

```text
abs(E_line + E_shift - E_exp) > prefilter_window_eV
```

则丢弃。

保留线的权重为：

```text
line_weight = (2J_upper + 1) * A
              * exp[-(E_line + E_shift - E_exp)^2 / (2 sigma^2)]
```

其中：

```text
sigma = fwhm_eV / 2.355
```

每个峰的理论线团中心：

```text
center_E = sum(E_line * line_weight) / sum(line_weight)
residual = E_exp - (center_E + E_shift)
score = sum(line_weight)
```

峰贡献：

```text
position_weight * peak_type_weight * residual^2
- strength_weight * peak_type_weight * log(score + rate_floor)
```

当前所有峰均为 `anchor`，因此：

```text
peak_type_weight = 1.0
```

总 loss：

```text
loss =
  sum_over_peaks[ residual^2 - log(score + floor) ]
  + complexity_penalty
  + missing_peak_penalty
```

当前设置：

```text
complexity_penalty = 2.0 * active_optional_template_count
missing_peak_penalty = 1000000.0 * missing_peak_count
```

loss 越小越好。负 loss 主要来自 `-log(score)` 项。

## 14. ODAT-SE 接入骨架

今天确认当前搜索器此前还不是 ODAT-SE，只是自写 FAC 搜索 runner。

随后实现了第一版 ODAT-SE-facing 接入骨架。

新增文件：

```text
scripts/odatse_fac_solver.py
scripts/run_odatse_fac_mapper.py
docs/odatse_integration.md
inputs/odatse_fac_mapper.toml
```

设计选择：

```text
x[0] = candidate_id
```

`candidate_id` 映射到一个合法候选：

```text
configuration templates + OptimizeRadial strategy
```

这样避免把离散 configuration 选择伪装成连续变量。

第一版推荐 ODAT-SE 算法：

```text
mapper
```

而不是 `minsearch`，因为当前主要是离散 configuration / optimization 搜索。

准备 ODAT-SE 输入：

```bash
python3 scripts/run_odatse_fac_mapper.py --prepare-only --clean
```

生成：

```text
runs/odatse_W46_v2/candidate_mesh.txt
runs/odatse_W46_v2/candidate_table.csv
inputs/odatse_fac_mapper.toml
```

当前完整合法候选数：

```text
48 candidates
```

由于当前环境没有安装 `odatse`，未实际调用 ODAT-SE runner。

但已验证 custom solver 的单点接口：

```text
candidate_id = 0
loss = 5000000.0
```

该 solver 会：

```text
candidate_id
-> configuration + OptimizeRadial
-> 生成 FAC input .py
-> 运行 FAC
-> 读取 W28a.tr
-> 计算当前 v2 loss
-> 返回 loss
```

若安装 ODAT-SE 后，可尝试：

```bash
python3 scripts/run_odatse_fac_mapper.py --clean
```

若未安装 ODAT-SE，可用本地 fallback：

```bash
python3 scripts/run_odatse_fac_mapper.py --local --clean
```
