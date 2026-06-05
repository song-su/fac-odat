# FAC + ODAT-SE daily summary, 2026-06-04

## 1. 今日主要工作

- 重新检查 Kimura et al., PRA 102, 032807 (2020) 的 I7+ Table I 复现问题
- 发现 2026-06-02 的 calibration 结论存在根本性匹配错误：程序按最近波长匹配了不相关跃迁
- 新增 `scripts/known.py`，按已知 configuration family 约束 Table I 峰的候选跃迁
- 重新完整运行 `inputs/target_case_v4_I_survey.py --clean`
- 用 known-transition matcher 重新评估 12 种 `OptimizeRadial` 策略
- 对 `Bi22.py` 参考输入中的 ionization configuration / `Structure` 用法做了比对

---

## 2. 关键纠正

### 2.1 旧 calibration 的问题

2026-06-02 的 survey 使用 `calibration_mode=True`，每个参考峰在所有 FAC `.tr`
跃迁中找最近波长。这个逻辑没有限制：

- 下能级必须是 ground `4d10`
- 上能级必须是论文指定的 `4d^-1 5s / 5p / 4f`
- 跃迁类型必须与 Table I 的 E1/E2 对应
- 具体 jj-coupling assignment 必须对应

因此旧结论中 `ground_plus_4d9_nl` 的好结果是伪匹配。例如 `26.24 nm`
附近的最近线实际来自：

```text
upper=230 -> lower=30
4d8.5p2 -> 4d9.4f1
```

这不是论文 Table I 的：

```text
(4d^-1_5/2 5s_1/2)_J=2 -> 4d10
```

所以旧的“复现论文 FAC 理论值”结论不成立。

### 2.2 `.tr` 列顺序问题

当前 FAC 1.1.5 ASCII `.tr` 行实际顺序为：

```text
upper_ilev upper_2J lower_ilev lower_2J dE[eV] gf A[s^-1] gf
```

旧 `scripts/run_configuration_search.py` 注释/读取逻辑把前四列理解为：

```text
upper_2J upper_ilev lower_2J lower_ilev
```

这会影响 `(2J+1)*A` 权重读取。今日新增的 `known.py` 按实际列顺序解析。

---

## 3. 新增 known-transition 诊断脚本

新增文件：

```text
scripts/known.py
tests/test_known.py
```

`known.py` 做的事情：

1. 解析 FAC `.en`，得到每个 `ILEV` 的 configuration label 和 FAC level label。
2. 解析 FAC `.tr`，按实际列顺序得到 upper/lower level、`2J`、`dE`、`A`。
3. 内置 I7+ Table I 的 6 条已知峰：

| 标签 | 粗略 family | 下能级 | 类型 |
|------|-------------|--------|------|
| a,b | `4d9.5s1` | `4d10` | E2 |
| d,e | `4d9.5p1` | `4d10` | E1 |
| f,g | `4d9.4f1` | `4d10` | E1 |

4. 对每个峰只列出对应 family 到 ground 的候选，不再允许任意最近波长线冒充。

测试 `tests/test_known.py` 专门验证：

- `4d8.5p2 -> 4d9.4f1` 这种不相关近邻线会被过滤
- `4d9.5s1 -> 4d10` 候选会被保留

已通过：

```bash
python3 -m unittest tests.test_known
python3 -m compileall scripts/known.py tests/test_known.py
```

---

## 4. 重新运行 OptimizeRadial survey

命令：

```bash
python3 scripts/run_configuration_search.py inputs/target_case_v4_I_survey.py --clean
```

输出：

```text
runs/search_W7_v4_survey/results.txt
runs/search_W7_v4_survey/loss_configuration_optimization.txt
```

旧 built-in calibration loss 仍给出：

```text
best = trial_0010, ground_plus_4d9_nl, loss = 0.0173
```

但这个 loss 仍然是旧的最近线匹配逻辑，因此不再作为 Table I 复现依据。

---

## 5. known-transition 重新评分结果

### 5.1 目标为论文 Table I 的 λth

用 `known.py` 对重新生成的 12 个 trial 评分，目标为论文 FAC 理论波长：

| rank | strategy | RMS (Å) | mean abs (Å) | max abs (Å) |
|------|----------|---------|--------------|-------------|
| 1 | `ground_only` | 0.922 | 0.790 | 1.394 |
| 2 | `4d9_4f_only` | 2.277 | 2.047 | 3.557 |
| 3 | `4p5_4d10_4f_only` | 2.739 | 2.193 | 5.267 |
| 4 | `ground_plus_4d9_4f_nl` | 4.701 | 3.448 | 10.007 |
| 5 | `ground_plus_4d9_nl` | 5.551 | 4.085 | 11.914 |

### 5.2 目标为实验 λex

用实验波长作为目标时，排名仍相同：

| rank | strategy | RMS (Å) | mean abs (Å) | max abs (Å) |
|------|----------|---------|--------------|-------------|
| 1 | `ground_only` | 0.550 | 0.433 | 1.094 |
| 2 | `4d9_4f_only` | 2.113 | 1.864 | 3.257 |
| 3 | `4p5_4d10_4f_only` | 2.430 | 1.947 | 4.967 |
| 4 | `ground_plus_4d9_4f_nl` | 4.427 | 3.205 | 9.707 |
| 5 | `ground_plus_4d9_nl` | 5.308 | 4.002 | 11.614 |

结论：按已知跃迁 family 限制后，目前最好的势是 `ground_only`，而不是
`ground_plus_4d9_nl`。

---

## 6. 精确 assignment 检查

进一步按 FAC label 粗略对应 Table I 的 jj assignment 检查 `ground_only`：

| 标签 | FAC label | λth target (nm) | calc (nm) | residual (Å) |
|------|-----------|-----------------|-----------|--------------|
| a | `4d+5(5)5.5s+1(1)4` | 26.24 | 25.9356 | +3.044 |
| b | `4d-3(3)3.5s+1(1)4` | 25.27 | 25.0047 | +2.653 |
| d | `4d-3(3)3.5p-1(1)2` | 19.45 | 19.3106 | +1.394 |
| e | `4d-3(3)3.5p+1(3)2` | 19.09 | 18.9573 | +1.327 |
| f | `4d+5(5)5.4f-1(5)2` | 16.56 | 16.4686 | +0.914 |
| g | `4d-3(3)3.4f-1(5)2` | 15.77 | 15.6840 | +0.860 |

即使使用最优 `ground_only`，仍然不能复现文章 Table I 的 FAC λth 到 0.1 Å
量级。当前差异是 Å 量级，说明问题已不是单纯找峰错误，而是 FAC structure
输入/势/RCI 细节没有复现文章。

---

## 7. `Bi22.py` 参考输入对比

检查 `Bi22.py` 后确认，参考输入将下一电离态配置写入同一个 `.en` 文件，但用
单独的 `Structure` 调用：

```python
fac.Structure(p+'b.en', ['n2', ..., 'n12'])
fac.Structure(p+'b.en', ['i1', 'i2', 'i3'])
```

随后电离截面使用：

```python
fac.CITable(p+'b.ci', ['n2', ..., 'n12'], ['i1', 'i2', 'i3'])
```

判断：

- 这种分开 `Structure` 的 ionization group 对 bound-bound Table I 波长基本不会有影响。
- 它对 CR/ionization channel 是必要的。
- 若目标是复现 Table I λth，核心应继续检查 46-electron `Structure` 子集、
  `OptimizeRadial` 策略、RCI/Breit/QED 显式设置和精确 jj assignment。

---

## 8. 当前结论

1. 2026-06-02 的 `ground_plus_4d9_nl` 最优结论是由错误最近线匹配导致的。
2. 按 Table I 已知 family 限制后，当前 12 策略中 `ground_only` 最好。
3. 即使 `ground_only` 也没有复现文章 λth，仍有 0.8-3.0 Å 偏差。
4. 下一个电离态 `4p6 4d9` 应按 `Bi22.py` 方式加入 CR/CI 流程，但不会解决
   bound-bound 波长差异。
5. 下一步应做 structure reproduction sweep：
   - 固定 Table I 精确 jj assignment
   - 扫 46-electron `Structure` 子集
   - 扫 `OptimizeRadial` groups
   - 检查 FAC Breit/QED/RCI 显式选项
   - 比较每条指定 upper -> `4d10` 的 λth 偏差

---

## 9. 新增/更新文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `scripts/known.py` | 新增 | I7+ Table I known-transition family matcher |
| `tests/test_known.py` | 新增 | 验证不相关近邻线不会被 known matcher 接受 |
| `docs/daily_summary_fac_odat_2026_06_04.md` | 新增 | 本日志 |

