# FAC + ODAT-SE daily summary, 2026-05-27

## 1. 今日主要工作

- 分析当前 loss 函数的物理含义与缺陷
- 确认 FAC `.tr` 文件的列格式与 2J 读取方式
- 新增 `min_A_value` 过滤选项
- 新增 `scoring_space` 可选参数（energy / wavelength）
- 创建 `inputs/target_case_v4.py`（波长空间评分版本）
- 对当前 loss 设计做了批判性评价

---

## 2. FAC `.tr` 文件格式确认

通过读取 `runs/search_W46_v2/trial_0003/W28a.tr` 确认：

实际文件中所有数据行均为 **8 列**格式：

```
upper_2J  upper_ilev  lower_2J  lower_ilev  dE[eV]  gf  A[s^-1]  gf
```

- `parts[0]` = upper_2J（整数，如 J=4.5 对应 2J=9）
- `parts[6]` = A（s⁻¹）
- `parts[7]` = gf（与 parts[5] 相同，含义待查）

代码中的 **10 列分支**（`parts[7]` 作为 A）在当前 FAC 设置下**从未被触发**，是死代码。

### gA 计算

```python
weight = (upper_2j + 1) * a_value   # = g_upper * A
```

`(upper_2J + 1)` 即 `g_upper = 2J+1`，gA 公式正确。

---

## 3. 新增 `min_A_value` 过滤选项

### 修改文件

```
scripts/run_configuration_search.py
inputs/target_case_v3.py
```

### 改动

`read_tr_ascii` 新增 `min_A=0.0` 参数：

```python
def read_tr_ascii(filename, min_A=0.0):
    ...
    if a_value < min_A:
        continue
```

过滤发生在解析阶段，被丢弃的线不进入 Gaussian 窗口计算。

### 用法（在 `SEARCH["scoring"]` 中设置）

```python
"min_A_value": None    # 不过滤（默认）
"min_A_value": 1e8     # 丢弃 A < 10^8 s^-1 的弱线
```

---

## 4. 新增 `scoring_space` 可选参数

### 背景

原有 loss 全部在能量（eV）空间计算 Gaussian 窗口和残差。
用波长（Å）计算在光谱学上更自然，且窗口宽度对所有峰物理含义一致。

### 修改文件

```
scripts/run_configuration_search.py
```

修改的函数：

| 函数 | 改动 |
|------|------|
| `build_v2_peak_groups` | `energy_shift` → `shift` + `hc`；`scoring_space` 分支 |
| `optimize_global_shift` | 用 `center_scoring` 计算 shift；sanity range 分空间读取 |
| `score_tr_file_v2` | 读取 `scoring_space` 和 `hc`；用 `residual_scoring` 计算 loss |

### scoring_space = "wavelength" 的计算方式

每条线的坐标转换：

```
x = hc / energy    # Å
```

Gaussian 窗口宽度：

```
sigma_x = (lambda_peak)^2 / hc * sigma_eV    # 由 fwhm_eV 换算
```

如果输入文件中指定了 `fwhm_angstrom`，则换算过程是可逆的（round-trip 精确）。

残差：

```
residual_angstrom = lambda_exp - (center_angstrom + lambda_shift)
```

Global shift 也在 Å 空间最优化。Sanity range 用 `sanity_range_angstrom`。

summary 新增字段：

```
center_angstrom, residual_angstrom, center_scoring, residual_scoring, scoring_space, shift
```

---

## 5. 新增 `inputs/target_case_v4.py`

基于 v3，主要设置变化：

| 参数 | v3 | v4 |
|------|----|----|
| `scoring_space` | `"energy"` | `"wavelength"` |
| `DEFAULT_PEAK["fwhm_eV"]` | `3.0` | `None` |
| `DEFAULT_PEAK["fwhm_angstrom"]` | `None` | `0.1` Å |
| `prefilter_window_eV` | `15.0` | `200.0` |
| `sanity_range` | `sanity_range_eV: [-12, 12]` | `sanity_range_angstrom: [-0.05, 0.05]` |
| `position_weight` | `1.0` | `1000.0` |

### position_weight 放大原因

波长模式下 `residual²` 单位为 Å²（典型值 ~0.01 Å²），而 `−log(score)` 为无量纲数（典型值 ~10–20）。若 `position_weight = 1.0`，位置项对 loss 贡献约 0.0001，完全被强度项淹没。设为 `1000.0` 后两项量级相当。

### fwhm_angstrom = 0.1 Å 换算为 eV

在峰 5.69 Å 处：
```
fwhm_eV = hc * fwhm_angstrom / lambda^2
        = 12398.4 * 0.1 / (5.69)^2
        = 38.3 eV
```

在峰 7.93 Å 处：
```
fwhm_eV = 12398.4 * 0.1 / (7.93)^2
        = 19.7 eV
```

用 `fwhm_angstrom` 而非 `fwhm_eV` 可对所有峰保持一致的波长窗口宽度。

---

## 6. 当前 loss 函数的批判性评价

### 公式回顾

```
loss = Σ_peaks [ position_weight * residual_x^2
               - strength_weight * log(score + floor) ]
     + complexity_penalty * optional_count
     + missing_peak_penalty * missing_count

score   = Σ (2J+1)*A * Gaussian(Δx)
center  = Σ(x_line * score_line) / Σ(score_line)   ← gA 加权均值
residual = x_exp - (center + shift)
```

### 主要缺陷

**1. 位置项实际失效**

`center` 是 gA 加权均值。只要窗口内有足够多的线，均值自动收敛到实验峰附近，`residual ≈ 0`。宽窗口（`fwhm_angstrom = 0.1 Å`）尤其如此。结果 loss 退化为 `−log(score)`，只比较 gA 总量。

**2. `−log(score)` 不区分一条强线与许多弱线**

```
score = 1e10  ← 1 条 gA = 1e10 的线
score = 1e10  ← 1000 条 gA = 1e7 的线
```

两者 loss 完全相同，但物理上一个产生尖锐可见峰，另一个是不可分辨的连续背景。

**3. gA 加权中心不是实验峰位置的物理对应**

实验观测到的峰位由最强线（或少数几条强线的 profile 卷积）决定，不是所有线的统计平均。弱线群会系统性地拖偏加权中心。

**4. 无绝对可观测性判断**

`−log(score)` 是相对排名，不判断 score 是否达到实验可观测量级。score 差 6 个数量级在 loss 中只差 `log(10^6) ≈ 14`，容易被其他项抹平。

**5. 大 global shift 没有惩罚**

shift = 0.001 Å 和 shift = 0.04 Å 的 trial 在 loss 里无区别。大 shift 本身可能说明 configuration / potential 的物理质量更差。

### 改进方向

**最小有效改动（推荐先做）：**

1. 把 `center_x` 改为窗口内 **gA 最大的那条线的波长**，而不是加权均值。5 行代码，让位置项真正起约束作用。

2. 加 `min_gA_required`：每个峰窗口内若不存在 gA 超过阈值的线，等同于 missing peak。

**较大改动：**

3. Top-N 线匹配：只取 gA 最大的前 N 条线参与评分，避免弱线污染统计。

4. 对 global shift 幅度加软惩罚：`loss += shift_penalty_weight * shift^2`。

---

## 7. 修改和新增的文件

| 文件 | 操作 | 内容 |
|------|------|------|
| `scripts/run_configuration_search.py` | 修改 | 新增 `min_A`、`scoring_space`、`hc` 支持 |
| `inputs/target_case_v3.py` | 修改 | 新增 `min_A_value: None` 到 scoring |
| `inputs/target_case_v4.py` | 新建 | 波长空间评分，`fwhm_angstrom = 0.1` |
