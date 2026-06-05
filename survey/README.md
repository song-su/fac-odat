# survey — FAC OptimizeRadial 搜索框架 / OptimizeRadial Survey Framework

[中文](#中文说明) | [English](#english-documentation)

---

## 中文说明

### 概述

本模块（`survey/`）提供了一套可复用的框架，用于系统扫描
[FAC（Flexible Atomic Code）](https://github.com/flexible-atomic-code/fac)
中 `OptimizeRadial` 的组态（configuration）组合，以寻找能最好地复现
已知实验/理论跃迁波长的最优设置。

核心思路：
- 给定 N 个可用组态族，枚举其 2^N − 1 种非空子集，分别作为 `OptimizeRadial` 的参数。
- 对每次试算，解析 FAC 输出的 `.en` / `.tr` 文件，按 **组态 + 总角动量 J** 精确匹配已知跃迁，计算 RMS 残差（单位 Å）。
- 按 RMS 从小到大排序，找出最优组态组合。
- 支持早停（early-stop）：RMS 低于阈值时立即取消剩余试算。

### 目录结构

```
survey/
├── README.md                  # 本文件
├── __init__.py
├── peaks.py                   # 已知跃迁数据结构（与原子代码无关）
├── scorer.py                  # 候选匹配与 RMS 评分（与原子代码无关）
├── config_loader.py           # 读取 .py / .yaml 配置文件
├── run_fac_survey.py          # FAC survey 主入口（编辑此文件的 defaults）
│
├── fac/                       # FAC 专用层
│   ├── __init__.py
│   ├── parser.py              # 解析 FAC ASCII .en / .tr 输出
│   ├── input_gen.py           # 生成 PFAC trial 脚本
│   └── runner.py              # 枚举试算、并发执行、评分
│
├── ions/                      # 离子数据层（每种离子一个文件）
│   ├── __init__.py
│   └── i7plus.py              # Pd-like I^7+（Z=53，46 电子）
│
└── configs/                   # FAC survey 配置文件（每种离子一个文件）
    ├── __init__.py
    └── i7plus_fac.py          # I^7+ FAC survey 配置（组态空间、参考波长等）
```

### 快速开始

#### 1. 运行 I^7+ survey

```bash
# 串行（调试用，只跑前几个试算时加 --max-combo-size 1）
python3 survey/run_fac_survey.py serial -n 1

# 多核并行（-n 指定进程数）
python3 survey/run_fac_survey.py parallel -n 8

# 设置早停阈值（RMS < 0.05 Å 时自动停止）
python3 survey/run_fac_survey.py parallel -n 8 --early-stop-rms 0.05
```

结果写入 `runs/i7_survey/`，每个试算一个子目录，包含：
- `trial.py` — 自动生成的 PFAC 脚本
- `*a.en` / `*a.tr` — FAC 输出
- `DONE` — 成功标志

#### 2. 修改默认参数

编辑 `survey/run_fac_survey.py` 顶部的 defaults 区块：

```python
DEFAULT_INPUT         = "survey/configs/i7plus_fac.py"
DEFAULT_OUTPUT        = "runs/i7_survey"
DEFAULT_JOBS          = 1
DEFAULT_MODE          = "serial"
DEFAULT_ION           = "i7plus"
DEFAULT_EARLY_STOP_RMS = None   # float（Å），None 表示跑完所有试算
```

#### 3. 生成离线 survey 包（用于集群）

```bash
python3 scripts/prepare_i7_full_survey_package.py \
    --output-dir runs/i7_cluster_package
```

生成的目录可完整复制到无网络的集群，包含所有 trial 脚本、`run_all.py` 和 `score_known.py`。

### 添加新离子

1. **创建离子数据文件** `survey/ions/<ion>.py`：
   - 定义 `BASE_CONFIG: dict[str, int]`（FAC 隐藏的基础壳层占据数）
   - 定义 `KNOWN_PEAKS: list[KnownPeak]`（已知跃迁，含组态+J+参考波长）

2. **创建 FAC 配置文件** `survey/configs/<ion>_fac.py`：
   - 定义 `CONFIGURATIONS`（组态族列表）、`OPTIMIZE_RADIAL`、`ION`、`FAC_INPUT`
   - 实现 `build_config()` 函数

3. **运行时指定离子**：
   ```bash
   python3 survey/run_fac_survey.py serial --ion <ion>
   ```

### 架构说明

本框架分三层，便于将来支持其他原子代码（如 HULLAC）：

| 层 | 模块 | 说明 |
|---|---|---|
| 代码无关层 | `peaks.py`, `scorer.py` | 已知跃迁定义、候选匹配、RMS 评分 |
| FAC 专用层 | `fac/parser.py`, `fac/input_gen.py`, `fac/runner.py` | 解析 FAC 输出、生成输入脚本、执行试算 |
| 离子数据层 | `ions/<ion>.py`, `configs/<ion>_fac.py` | 特定离子的已知跃迁和配置空间 |

---

## English Documentation

### Overview

The `survey/` module provides a reusable framework for systematically scanning
`OptimizeRadial` configuration combinations in
[FAC (Flexible Atomic Code)](https://github.com/flexible-atomic-code/fac)
to find the setting that best reproduces known experimental or theoretical
transition wavelengths.

Core idea:
- Given N available configuration families, enumerate all 2^N − 1 non-empty
  subsets and use each as the argument to `OptimizeRadial`.
- For each trial, parse the FAC `.en` / `.tr` output and match known transitions
  by **configuration + total angular momentum J** (not nearest-neighbour).
  Compute the RMS residual in Å.
- Rank trials by ascending RMS to find the optimal configuration combination.
- Optional early stopping: cancel remaining trials when RMS drops below a
  threshold.

### Directory Layout

```
survey/
├── README.md                  # This file
├── __init__.py
├── peaks.py                   # Known-transition data structures (code-agnostic)
├── scorer.py                  # Candidate matching and RMS scoring (code-agnostic)
├── config_loader.py           # Load .py / .yaml configuration files
├── run_fac_survey.py          # FAC survey entry point (edit defaults here)
│
├── fac/                       # FAC-specific layer
│   ├── __init__.py
│   ├── parser.py              # Parse FAC ASCII .en / .tr output files
│   ├── input_gen.py           # Generate PFAC trial scripts
│   └── runner.py              # Enumerate trials, run concurrently, score
│
├── ions/                      # Per-ion data (one file per ion)
│   ├── __init__.py
│   └── i7plus.py              # Pd-like I^7+ (Z=53, 46 electrons)
│
└── configs/                   # FAC survey configurations (one file per ion)
    ├── __init__.py
    └── i7plus_fac.py          # I^7+ FAC survey config (configuration space, etc.)
```

### Quick Start

#### 1. Run the I^7+ survey

```bash
# Serial mode (for debugging; limit scope with --max-combo-size 1)
python3 survey/run_fac_survey.py serial -n 1

# Parallel (set -n to the number of worker processes)
python3 survey/run_fac_survey.py parallel -n 8

# With early stopping (halt when RMS < 0.05 Å)
python3 survey/run_fac_survey.py parallel -n 8 --early-stop-rms 0.05
```

Results are written to `runs/i7_survey/`. Each trial gets its own
subdirectory containing:
- `trial.py` — auto-generated PFAC script
- `*a.en` / `*a.tr` — FAC output files
- `DONE` — success marker

#### 2. Edit default parameters

Open `survey/run_fac_survey.py` and modify the defaults block at the top:

```python
DEFAULT_INPUT         = "survey/configs/i7plus_fac.py"
DEFAULT_OUTPUT        = "runs/i7_survey"
DEFAULT_JOBS          = 1
DEFAULT_MODE          = "serial"
DEFAULT_ION           = "i7plus"
DEFAULT_EARLY_STOP_RMS = None   # float in Å, or None to run all trials
```

#### 3. Generate an offline survey package (for clusters)

```bash
python3 scripts/prepare_i7_full_survey_package.py \
    --output-dir runs/i7_cluster_package
```

The generated directory is self-contained and can be copied to an air-gapped
cluster. It includes all trial scripts, `run_all.py`, and `score_known.py`.

### Adding a New Ion

1. **Create the ion data file** `survey/ions/<ion>.py`:
   - Define `BASE_CONFIG: dict[str, int]` (shells hidden by FAC at block-reference occupancy)
   - Define `KNOWN_PEAKS: list[KnownPeak]` (known transitions with config, J, and reference wavelength)

2. **Create the FAC config file** `survey/configs/<ion>_fac.py`:
   - Define `CONFIGURATIONS`, `OPTIMIZE_RADIAL`, `ION`, `FAC_INPUT`
   - Implement `build_config()` 

3. **Specify the ion at runtime**:
   ```bash
   python3 survey/run_fac_survey.py serial --ion <ion>
   ```

### Architecture

The framework is split into three layers to allow future support for other
atomic codes (e.g. HULLAC):

| Layer | Modules | Responsibility |
|---|---|---|
| Code-agnostic | `peaks.py`, `scorer.py` | Known-transition definitions, candidate matching, RMS scoring |
| FAC-specific | `fac/parser.py`, `fac/input_gen.py`, `fac/runner.py` | Parse FAC output, generate input scripts, run trials |
| Ion data | `ions/<ion>.py`, `configs/<ion>_fac.py` | Per-ion known transitions and configuration space |

### Known-Transition Matching

Transitions are matched by **upper_config + upper_2j + lower_config + lower_2j**,
not by nearest wavelength across the full line list. This prevents false matches
when many FAC lines cluster near the target wavelength (a common failure mode
for satellite-line spectra). Within the filtered set the closest line in
wavelength is selected.

The `BASE_CONFIG` dictionary (e.g. `{"4p": 6, "4d": 10}` for I^7+) tells the
scorer which closed-shell occupancies FAC omits from its level labels, allowing
it to reconstruct full configuration strings for cross-block transitions.

### Reference

Kimura et al., *Phys. Rev. A* **102**, 032807 (2020) — Table I provides the
FAC theoretical wavelengths (λ_th) used as reference targets for the I^7+ survey.
