# FAC + ODAT-SE daily summary, 2026-06-05

## 1. 今日主要工作

- 继续整理 I7+ Table I 复现问题中 FAC 层的可变因素
- 验证 `fac.Config('... 5[s,p,d,f]', group='n')` 与同 group 多行展开是否等价
- 验证把同一 configuration family 拆成多个 FAC group 后会改变 FAC 结果
- 在主生成器中加入 `nl/mk` 的分组模式选项
- 为 I7+ 生成可拷贝到服务器/超算运行的完整 FAC survey package
- 将批量运行入口从 shell 改为 Python runner

---

## 2. FAC group 展开验证

今天重点确认了一个容易混淆的问题：

```python
fac.Config('4p6 4d9 5[s,p,d,f]', group='n4')
```

和：

```python
fac.Config('4p6 4d9 5s', group='n4')
fac.Config('4p6 4d9 5p', group='n4')
fac.Config('4p6 4d9 5d', group='n4')
fac.Config('4p6 4d9 5f', group='n4')
```

是否等价。

### 2.1 同 group 内语法展开

新建实验输入：

```text
runs/experiment_split_groups/trial_0010_same_group/trial_0010_same_group.py
```

该输入只把 bracket 写法展开成多行 `fac.Config`，但保持原 group 名称不变：

```text
4p6 4d9 5s/5p/5d/5f 仍在 n4
4p6 4d9 6s/6p/6d/6f 仍在 n5
4p5 4d10 5s/5p/5d/5f 仍在 n7
```

`OptimizeRadial`、`Structure`、`TransitionTable` 的 group 列表保持与原始
`trial_0010` 一致。

结果：

```text
.en 行数: 678 vs 678
.tr 行数: 26338 vs 26338

known.py:
compact    RMS = 5.550943 A
same_group RMS = 5.550943 A
```

进一步比较 `.tr` 数值列：

```text
upper/lower/2J: 完全一致
dE:             完全一致
gf:             最大差 1e-7
A:              最大相对差约 1e-7
```

结论：

```text
同一个 FAC group 内的 bracket 写法与多行展开在能级和跃迁能量上等价。
差异只在时间戳和极小浮点末位。
```

### 2.2 拆成不同 group

此前也跑了 split-group 对照，即把：

```text
4p6 4d9 5s, 5p, 5d, 5f
```

拆成不同 FAC group。

结果显示 FAC 结果会改变。例如目标为论文 Table I 的 FAC 理论波长时：

| case | RMS (A) | mean abs (A) | max abs (A) |
|------|---------|--------------|-------------|
| compact `ground_only` | 0.922 | 0.790 | 1.394 |
| split `ground_only` | 0.861 | 0.785 | 1.199 |
| compact `ground_plus_4d9_nl` | 5.551 | 4.085 | 11.914 |
| split `ground_plus_4d9_nl` | 5.439 | 3.984 | 11.609 |

结论：

```text
FAC group 边界不是纯命名；拆成不同 group 会改变结果。
```

---

## 3. 新增 `ACTIVE_GROUP_BY`

今天在 FAC 输入生成器中加入了 `group_by` 支持。

修改核心文件：

```text
scripts/generate_fac_input.py
```

新增行为：

```python
group_by = "n"  # nl 默认，按 n 分组
group_by = "l"  # nl 拆成每个 n/l 子配置一个 group
group_by = "m"  # mk 默认，按 m 分组
group_by = "k"  # mk 拆成每个 m/k 子配置一个 group
```

在 I7+ 主输入和 survey 输入中新增统一开关：

```python
ACTIVE_GROUP_BY = {
    "nl": "n",
    "mk": "m",
}
```

如果需要改成拆分模式：

```python
ACTIVE_GROUP_BY = {
    "nl": "l",
    "mk": "k",
}
```

修改文件：

```text
inputs/target_case_v2.py
inputs/target_case_v3.py
inputs/target_case_v4.py
inputs/target_case_v4_I.py
inputs/target_case_v4_I_survey.py
scripts/generate_fac_input.py
```

这里特别注意：

```text
group_by 改变的是 FAC group 边界，不只是输出名字。
```

---

## 4. FAC 层变量整理

今天明确区分了 FAC 计算本身的变量和 scoring/search 后处理变量。

在当前 I7+ Table I bound-bound 复现问题中，如果固定：

```text
所有输入组态都进入 Structure
TransitionTable 覆盖全部 bound groups
SetUTA(0)
```

则 FAC 层主要可变因素是：

1. 输入 configuration 集合
2. `nl/mk` 的 FAC group 分组方式，即 `n/m` vs `l/k`
3. `OptimizeRadial` 使用哪些 group
4. `OptimizeRadial` group 权重
5. `ConfigEnergy(0) -> OptimizeRadial -> ConfigEnergy(1)` 的势优化流程细节
6. `Closed(...)`、Breit/QED/RCI 等更底层 FAC 物理开关

今日决定：

```text
暂时不扫 OptimizeRadial weights。
```

当前优先做：

```text
已知 configuration family 全组合 OptimizeRadial
分别在 n/m 分组和 l/k 分组下运行
```

---

## 5. I7+ 全流程运行包

新增脚本：

```text
scripts/prepare_i7_full_survey_package.py
```

该脚本生成一个独立运行包：

```text
runs/i7_full_fac_survey_package/
```

包内文件：

```text
README.md
known.py
manifest.csv
metadata.json
run_all.py
score_known.py
target_case_v4_I_survey.py
trials/
```

运行包覆盖两种分组模式：

| mode | nl | mk |
|------|----|----|
| `nm` | 按 `n` 分组 | 按 `m` 分组 |
| `lk` | 按 `l` 分组 | 按 `k` 分组 |

I7+ survey 当前有 9 个已知 configuration family：

```text
4p6_4d10
4p6_4d9_4f
4p6_4d9_nl
4p5_4d10_4f
4p5_4d10_5l
4p6_4d8_5s2
4p6_4d8_5p2
4p6_4d8_5d2
4p6_4d8_5s1_5p1
```

每种分组模式枚举所有非空 `OptimizeRadial` family 组合：

```text
2^9 - 1 = 511
```

两种模式合计：

```text
511 * 2 = 1022 trials
```

注意：

```text
这里不是对拆分后的每个 5s/5p/... 做 2^N 组合。
组合单位仍是 template family。
```

---

## 6. Python runner

用户要求不要用 shell 唤起批量任务，因此今天将运行包入口改为 Python：

```text
runs/i7_full_fac_survey_package/run_all.py
```

服务器/超算上运行：

```bash
python3 run_all.py --jobs 12 --mode serial
```

如果服务器 FAC 支持 OpenMP：

```bash
python3 run_all.py --jobs 12 --mode openmp
```

参数：

```text
--jobs    并行 trial 进程数
--mode    传给每个 PFAC trial.py 的模式：serial/openmp/mpi
--python  指定 Python 可执行文件
--force   即使 trial 目录已有 DONE 也强制重跑
```

运行完成后评分：

```bash
python3 score_known.py
```

评分结果写入：

```text
runs/i7_full_fac_survey_package/known_scores.csv
```

`score_known.py` 使用包内复制的：

```text
known.py
```

因此运行包可以单独拷贝到服务器，不依赖原 repo 路径。

---

## 7. 验证

今天完成的主要验证：

```bash
python3 -m unittest tests.test_prepare_i7_full_survey_package tests.test_generate_fac_input tests.test_known
```

结果：

```text
Ran 7 tests in 0.332s
OK
```

语法检查：

```bash
python3 -m py_compile scripts/prepare_i7_full_survey_package.py tests/test_prepare_i7_full_survey_package.py
```

运行包生成：

```bash
python3 scripts/prepare_i7_full_survey_package.py --output-dir runs/i7_full_fac_survey_package
```

输出：

```text
runs/i7_full_fac_survey_package
trial_count=1022
```

运行包检查：

```text
run_all.py --help 可正常显示参数
score_known.py 在未运行 FAC 时可启动并标记 missing_output
```

---

## 8. 新增/更新文件（上午）

| 文件 | 操作 | 说明 |
|------|------|------|
| `scripts/generate_fac_input.py` | 修改 | 支持 `group_by = n/l/m/k` |
| `inputs/target_case_v2.py` | 修改 | 透传 `group_by` / `ACTIVE_GROUP_BY` |
| `inputs/target_case_v3.py` | 修改 | 透传 `group_by` / `ACTIVE_GROUP_BY` |
| `inputs/target_case_v4.py` | 修改 | 透传 `group_by` / `ACTIVE_GROUP_BY` |
| `inputs/target_case_v4_I.py` | 修改 | 新增 `ACTIVE_GROUP_BY` |
| `inputs/target_case_v4_I_survey.py` | 修改 | 新增 `ACTIVE_GROUP_BY` |
| `scripts/prepare_i7_full_survey_package.py` | 新增 | 生成 I7+ 全组合 FAC 运行包 |
| `tests/test_generate_fac_input.py` | 新增 | 测试 `nl/mk` 分组与同输入混合场景 |
| `tests/test_prepare_i7_full_survey_package.py` | 新增 | 测试 1022 trial 运行包生成 |
| `runs/i7_full_fac_survey_package/` | 新增 | 服务器/超算运行包 |

---

## 9. known.py 普适化重构

### 9.1 动机

`known.py` 原版对 I7+ 硬编码，`prepare_i7_full_survey_package.py` 缺少
用户区 / 通用库分层。参照 `inputs/target_case_v4.py` 的结构（用户区 + 通用
函数），对两个脚本做了完整重构。

### 9.2 跃迁标签自动推导

新增 `derive_transition_label(upper_config, lower_config, base_config=None)`：

- 解析 FAC `.en` 第 8 列（column 7）的短 config 标签（如 `4d9.5s1`）
- 比较 upper / lower 的壳层占据差，对单电子变化返回 `"5s→4d"` 形式的标签
- 返回值是 `KnownPeak.transition` 和 `Candidate.transition` 的 property，
  不需要手填

### 9.3 满轨道隐藏问题与 BASE_CONFIG 修复

FAC 按 NBLOCK 用不同参考配置隐藏满轨道：

| Block | 被隐藏的满轨道 | config 标签例 |
|-------|-------------|--------------|
| `4d` 系列 | `4p6` | `4d9.5s1` |
| `4p5` 系列 | `4d10` | `4p5.4f1` |

直接比较跨 block 的短标签会丢失信息，`derive_transition_label` 返回 None。

**修复**：新增用户区变量 `BASE_CONFIG = {"4p": 6, "4d": 10}`，
保存活性壳层的满占据参考值。函数先用 `{**base_config, **parsed}` 把两边
缺失的壳层补回来，再求差：

```python
# 4p5.4f1 -> 4d10（跨 block）
derive_transition_label("4p5.4f1", "4d10", {"4p":6,"4d":10})
# → "4f→4p"   ✓
```

同 block 的 6 条 I7+ Table I 跃迁不受影响，均正常给出 `"5s→4d"` 等标签。

### 9.4 通用函数接口

| 变更前 | 变更后 |
|--------|--------|
| `KNOWN_I7_PEAKS`（硬编码列表） | `KNOWN_PEAKS`（用户区，可换 ion）|
| `find_known_i7_candidates(en, tr, ...)` | `find_known_candidates(peaks, en, tr, ...)` |
| `jj_assignment` 字段（上一版本错误方向）| 移除；改为自动推导的 `transition` property |

`KNOWN_I7_PEAKS` 和 `find_known_i7_candidates` 保留为向后兼容别名。

`format_candidates` 输出新增 `transition` 列。

---

## 10. run_fac_survey.py — 单步直接运行

### 10.1 动机

原来是两步：

```
prepare_i7_full_survey_package.py  →  生成全部 1022 个 trial.py
run_all.py                         →  遍历并运行它们
```

新脚本 `scripts/run_fac_survey.py` 合并为一步：按需生成 `trial.py`，
立即运行，无需预生成阶段。

### 10.2 用法

```bash
# 最简（全用脚本顶部默认值）
python3 scripts/run_fac_survey.py

# 指定 mode
python3 scripts/run_fac_survey.py openmp

# 指定 mode + 并行进程数
python3 scripts/run_fac_survey.py openmp -n 12

# bsub 投递（bsub 申请核数，脚本拿到的只是 openmp）
bsub -n 12 python3 scripts/run_fac_survey.py openmp
```

`mode` 是位置参数（可缺省），`-n` 是并行 trial 进程数，与其他 FAC 脚本
惯例一致。

### 10.3 CLI 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `mode`（位置） | `FAC_MODE`（用户区） | `serial` / `openmp` / `mpi` |
| `-n CORES` | `JOBS`（用户区） | 并行 trial 进程数 |
| `--force` | False | 忽略 DONE 文件，强制重跑 |
| `--score-only` | False | 不运行 FAC，只重新打分 |
| `--input` | `INPUT_FILE`（用户区） | survey 配置文件 |
| `--output` | `OUTPUT_DIR`（用户区） | 输出目录 |

### 10.4 关于 bsub 的核数对应关系

```
bsub -n 12    → 告诉调度器申请 12 核（bsub 参数，不传给 Python）
-n 12         → 告诉脚本同时运行 12 个 FAC trial 进程
```

两者需要手动保持一致。若每个 trial 内部也用 OpenMP（`mode=openmp`），
则总占用核数 ≈ `-n` × `OMP_NUM_THREADS`，应不超过 bsub 申请量。

---

## 11. 新增/更新文件（下午）

| 文件 | 操作 | 说明 |
|------|------|------|
| `scripts/known.py` | 重构 | 用户区 + 通用库分层；`KNOWN_PEAKS`；`BASE_CONFIG`；`derive_transition_label`；`transition` property |
| `scripts/prepare_i7_full_survey_package.py` | 修改 | 新增用户区注释；score script 改用 `find_known_candidates(KNOWN_PEAKS,...)`；README 通用化 |
| `scripts/run_fac_survey.py` | 新增 | 单步直接运行 survey；`mode` 位置参数；`-n` 并行数；bsub 兼容 |

---

## 12. 下一步（上午）

1. 将 `scripts/` 和 `inputs/target_case_v4_I_survey.py` 拷贝到服务器。
2. 在脚本顶部设置 `JOBS`，运行：

```bash
python3 run_fac_survey.py openmp -n 12
# 或 bsub 投递：
bsub -n 12 python3 run_fac_survey.py openmp
```

3. 完成后查看 `runs/i7_survey/known_scores.csv`，找 RMS 最小的
   势优化 / 分组组合。
4. 对获胜组合做精细 structure reproduction sweep（Breit/QED/RCI 显式开关）。

---

## 13. survey/ 模块完全整合（下午）

### 13.1 背景

上午将主要逻辑移入 `survey/` 包（commit `74c6642`、`b5989bc`），但存在以下问题：

- `survey/configs/` 目录尚未创建，FAC 配置文件仍在 `inputs/`。
- `survey/run_fac_survey.py` 不存在，入口在 `scripts/`。
- `REFERENCE_PEAKS`（configs 里）和 `KNOWN_PEAKS`（ions 里）数据重复，
  修改波长需要改两个文件。
- `survey/ions/i7plus.py` 的 docstring 写着已废弃的旧路径。

### 13.2 目录整合

新建 `survey/configs/`，将 I7+ FAC 配置从 `inputs/target_case_v4_I_survey.py`
迁移至 `survey/configs/i7plus_fac.py`。

整合后 `survey/` 目录结构：

```
survey/
├── README.md              # 中英文双语说明（新增）
├── __init__.py
├── peaks.py               # KnownPeak 等数据结构（代码无关层）
├── scorer.py              # 候选匹配与 RMS 评分（代码无关层）
├── config_loader.py       # 读取 .py/.yaml 配置
├── run_fac_survey.py      # FAC survey 主入口（新增；入口从 scripts/ 迁移）
├── fac/
│   ├── parser.py          # 解析 FAC .en/.tr
│   ├── input_gen.py       # 生成 PFAC trial 脚本
│   └── runner.py          # 枚举/运行/评分
├── ions/
│   └── i7plus.py          # shim → survey.configs.i7plus_fac
└── configs/
    ├── __init__.py
    └── i7plus_fac.py      # I7+ 全部参数（新增；原来分散在两处）
```

相关 `scripts/` 文件全部变为单行 shim：

| 文件 | 变更 |
|------|------|
| `scripts/run_fac_survey.py` | → `runpy` shim，指向 `survey/run_fac_survey.py` |
| `inputs/target_case_v4_I_survey.py` | → shim，re-export `survey.configs.i7plus_fac` |

### 13.3 KNOWN_PEAKS / REFERENCE_PEAKS 合并

整合前问题：

| 数据 | 位置 | 作用 |
|------|------|------|
| `REFERENCE_PEAKS` | `survey/configs/i7plus_fac.py` | 只用于在生成的 `trial.py` 里写注释 |
| `KNOWN_PEAKS` + `BASE_CONFIG` | `survey/ions/i7plus.py` | 评分用（RMS 目标波长、config+J 匹配） |

两处包含相同波长数据，修改参考波长需要同步改两个文件，容易遗漏。

整合方案：

1. 将 `KNOWN_PEAKS` 和 `BASE_CONFIG` 从 `survey/ions/i7plus.py` 移入
   `survey/configs/i7plus_fac.py` 文件顶部，集中为"用户需要编辑的参数"区块。
2. 删除独立的 `REFERENCE_PEAKS` 列表；`build_config()` 改为从 `KNOWN_PEAKS`
   的 `paper_fac_nm` 字段自动生成 `reference_peaks`（只是注释用途）。
3. `survey/ions/i7plus.py` 变为单行 shim：

```python
from survey.configs.i7plus_fac import KNOWN_PEAKS, BASE_CONFIG  # noqa: F401
```

### 13.4 单一编辑入口

整合完成后，对 I7+ 做任何参数修改只需编辑一个文件：

```
survey/configs/i7plus_fac.py
```

| 参数 | 位置 |
|------|------|
| 已知跃迁参考波长（`paper_fac_nm`、`exp_nm`） | `KNOWN_PEAKS` |
| jj 指定（`upper_2j`、`lower_2j`、config） | `KNOWN_PEAKS` |
| FAC 隐藏壳层基准（`BASE_CONFIG`） | 紧接 `KNOWN_PEAKS` |
| 输入组态族 | `CONFIGURATIONS` |
| `OptimizeRadial` 手工策略列表 | `OPTIMIZE_RADIAL` |
| 原子参数（Z、K、荷电态） | `ION` |
| FAC 运行参数 | `FAC_INPUT` |

survey 运行参数（进程数、输出目录等）仍在 `survey/run_fac_survey.py` 顶部：

```python
DEFAULT_INPUT          = "survey/configs/i7plus_fac.py"
DEFAULT_OUTPUT         = "runs/i7_survey"
DEFAULT_JOBS           = 1
DEFAULT_MODE           = "serial"
DEFAULT_ION            = "i7plus"
DEFAULT_EARLY_STOP_RMS = None
```

### 13.5 双语 README

新增 `survey/README.md`，中英文双语，覆盖：

- 框架概述与三层架构（代码无关层 / FAC 专用层 / 离子数据层）
- 快速开始（运行 I7+ survey、修改参数、生成集群运行包）
- 添加新离子的步骤
- known-transition 匹配原理说明

### 13.6 测试

所有 7 个单测仍通过：

```bash
python3 -m unittest discover -s tests -v
# Ran 7 tests in 0.327s  OK
```

### 13.7 新增/更新文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `survey/configs/__init__.py` | 新增 | configs 包初始化 |
| `survey/configs/i7plus_fac.py` | 新增 | I7+ 全部参数（含 KNOWN_PEAKS、BASE_CONFIG、CONFIGURATIONS 等）|
| `survey/run_fac_survey.py` | 新增 | FAC survey 主入口；DEFAULT_INPUT 指向 survey/configs/ |
| `survey/README.md` | 新增 | 中英文双语文档 |
| `survey/ions/i7plus.py` | 简化为 shim | 从 survey.configs.i7plus_fac 导入 |
| `scripts/run_fac_survey.py` | 简化为 shim | runpy 转发到 survey/run_fac_survey.py |
| `inputs/target_case_v4_I_survey.py` | 简化为 shim | re-export survey.configs.i7plus_fac |
| `scripts/prepare_i7_full_survey_package.py` | 修改 | DEFAULT_INPUT 改指 survey/configs/i7plus_fac.py |
| `tests/test_prepare_i7_full_survey_package.py` | 修改 | 配置路径与输出文件名更新 |

---

## 14. 下一步

1. 将 repo 拷贝到服务器，运行：

```bash
python3 survey/run_fac_survey.py parallel -n 12
```

2. 完成后查看 `runs/i7_survey/` 中的 `known_scores.csv`，找 RMS 最小组合。
3. 对获胜组合做精细 structure reproduction sweep（Breit/QED/RCI 显式开关）。
4. 若需支持新离子，按 README 中"添加新离子"一节新建
   `survey/configs/<ion>_fac.py`，修改 `survey/run_fac_survey.py` 的 `DEFAULT_ION`。

