# FAC + ODAT-SE daily summary, 2026-05-25

## FAC input generation: exhaustive configuration sets

今天澄清了一个重要问题：用户指出的不是 ODAT-SE 候选表数量问题，而是生成
FAC 输入文件时 `fac.Config(...)` 内容的问题。

正确语义如下：

```text
一个 FAC 输入 .py 文件 = 一个 configuration set
```

因此，如果共有 9 组 configuration，其中第 1 组 ground configuration 必须包含，
则合法的非空 set 不是 `2^9 - 1 = 511`，而是：

```text
2^(9 - 1) = 256
```

原因是 ground configuration 固定存在，只对剩余 8 个 optional configuration 做
on/off 组合。

每个生成出来的 FAC 输入文件内部，`fac.Config(...)` 应包含该 set 中所有被选中
的 configuration。也就是说，完整枚举时必须存在一个“全加”的 FAC 输入文件，
其中包含：

```text
ground + all optional configurations
```

注意：如果某个 configuration template 是 `nl` family，它会在 FAC 输入中展开成
多行 `fac.Config(...)`，例如：

```python
fac.Config('3p6 3d9 4[s,p,d,f]', group='n3')
fac.Config('3p6 3d9 5[s,p,d,f,g]', group='n4')
fac.Config('3p6 3d9 6[s,p,d,f,g,h]', group='n5')
fac.Config('3p6 3d9 7[s,p,d,f,g,h,i]', group='n6')
```

所以 template 数量与 `fac.Config(...)` 行数不一定一一对应。

## Code change

之前 `inputs/target_case_v2.yaml` 和 `inputs/target_case_v2.py` 中使用：

```text
search.method = "greedy_forward_selection"
```

这只会生成前向选择路径上的候选，不保证覆盖所有 configuration set，因此可能
看不到“全加”的 FAC 输入文件。

今天将默认搜索方式改为完整枚举：

```text
search.method = "grid_search"
```

修改文件：

```text
inputs/target_case_v2.yaml
inputs/target_case_v2.py
scripts/run_configuration_search.py
```

`scripts/run_configuration_search.py` 现在显式支持：

```text
grid_search
exhaustive_grid
greedy_forward_selection
```

未知 `search.method` 会直接报错，避免静默落到错误搜索逻辑。

## Verification

当前 v2 配置实际有 5 个 template：

```text
1 required ground template
4 optional templates
```

因此完整 configuration set 数量为：

```text
2^4 = 16
```

由于同时枚举合法的 OptimizeRadial strategy，当前总 trial 数为：

```text
48
```

直接检查完整枚举中的最后一个 trial，已确认它包含全加 configuration set：

```text
ground_3p6_3d10
hole_3d9_nl
hole_3p5_3d10_nl
hole_3d8_4s2
hole_3p5_3d9_4s2
```

对应生成的 FAC 输入中包含 ground、两个 `nl` family 展开项，以及两个额外的
single configuration：

```python
fac.Config('3p6 3d10', group='n2')
fac.Config('3p6 3d9 4[s,p,d,f]', group='n3')
fac.Config('3p6 3d9 5[s,p,d,f,g]', group='n4')
fac.Config('3p6 3d9 6[s,p,d,f,g,h]', group='n5')
fac.Config('3p6 3d9 7[s,p,d,f,g,h,i]', group='n6')
fac.Config('3p5 3d10 4[s,p,d,f]', group='n7')
fac.Config('3p5 3d10 5[s,p,d,f,g]', group='n8')
fac.Config('3p5 3d10 6[s,p,d,f,g,h]', group='n9')
fac.Config('3p5 3d10 7[s,p,d,f,g,h,i]', group='n10')
fac.Config('3p6 3d8 4s2', group='n11')
fac.Config('3p5 3d9 4s2', group='n12')
```

模拟 9 个 template 的情况时，枚举器给出：

```text
1 required + 8 optional -> 256 configuration sets
```

这符合用户指出的组合数要求。

## Python target input portability and output naming

今天继续整理 `inputs/target_case_v2.py`，目标是减少换离子时需要手动同步修改的
路径，并让输出文件扩展名符合当前使用习惯。

### CSV extension changed to TXT

将 v2 搜索和 ODAT-SE 相关输出文件名从 `.csv` 改为 `.txt`：

```text
runs/search_W46_v2/results.txt
runs/search_W46_v2/loss_configuration_optimization.txt
runs/odatse_W46_v2/fac_results.txt
runs/odatse_W46_v2/candidate_table.txt
runs/odatse_W46_v2/loss_configuration_optimization.txt
```

修改文件：

```text
inputs/target_case_v2.py
inputs/target_case_v2.yaml
inputs/odatse_fac_mapper.toml
scripts/run_configuration_search.py
scripts/odatse_fac_solver.py
scripts/run_odatse_fac_mapper.py
```

注意：当前只是把生成文件扩展名改为 `.txt`，表格内容仍使用 Python `csv`
模块写入，因此内部仍是逗号分隔表格。

### Automatic ion-dependent names

为 `inputs/target_case_v2.py` 增加自动命名逻辑。现在只需要修改：

```python
ION = {
    "element": "W",
    "Z": 74,
    "charge_state": 46,
    "K": 28,
}
```

默认会自动生成：

```text
output_prefix = {element}{K}
potential_file = {element}{charge_state}.pot
work_dir = runs/search_{element}{charge_state}_v2
generated_dir = generated/search_{element}{charge_state}_v2
results_file = runs/search_{element}{charge_state}_v2/results.txt
```

例如把离子改成 Ta45、`K = 28` 时，自动得到：

```text
output_prefix = Ta28
potential_file = Ta45.pot
work_dir = runs/search_Ta45_v2
generated_dir = generated/search_Ta45_v2
results_file = runs/search_Ta45_v2/results.txt
```

同时将 `scripts/run_odatse_fac_mapper.py` 的默认 `--output-dir` 改为从 target
配置推导：

```text
runs/search_Ta45_v2 -> runs/odatse_Ta45_v2
```

如果需要固定自定义路径，可以在 `RUN_NAMING` 中显式设置 `work_dir`、
`generated_dir` 或 `results_file`。

### Compatibility check

已对以下文件做 Python 3.6 语法解析检查和当前 Python 的 `compile()` 检查：

```text
inputs/target_case_v2.py
scripts/config_loader.py
scripts/generate_fac_input.py
scripts/odatse_fac_solver.py
scripts/run_configuration_search.py
scripts/run_odatse_fac_mapper.py
```

检查通过。没有实际运行 FAC 或 ODAT-SE。

## Must-include configuration input and mk expansion

为表达“根据物理猜想，某几组 configuration 必须出现在每个候选 FAC 输入中”的
需求，新增了一个独立输入文件：

```text
inputs/target_case_v2_must_include.py
```

该文件继承 `inputs/target_case_v2.py` 的大部分设置，只在顶部集中标注用户通常
需要修改的位置。

### required=True / False

在 `CONFIGURATIONS` 中，每一项现在可以显式写：

```python
{"config": "3p6 3d9 nl", "required": True}
{"config": "3p6 3d8 4s2", "required": False}
```

语义为：

```text
required=True  -> 每个 trial 都必须包含该 template
required=False -> 作为 optional template，由 grid_search 做 on/off 枚举
```

因此，如果有 3 个 required template 和 2 个 optional template，则 configuration
set 数量为：

```text
2^2 = 4
```

如果同时开启 `vary_optimize_radial_strategies`，实际 trial 数还会再乘以合法的
`OptimizeRadial` strategy 数量。

运行方式：

```bash
python3 scripts/run_configuration_search.py inputs/target_case_v2_must_include.py --clean
```

输出目录后缀设为：

```text
v2_must_include
```

避免覆盖默认 v2 结果。

### nl and mk expansion

用户进一步提出：除了已有的 `nl` 默认范围，还希望能定义另一组类似变量，例如：

```python
DEFAULT_NL = {
    "n": [4, 5, 6, 7],
    "l": [0, 1, 2, 3, 4, 5, 6],
    "m": [5, 6, 7, 8],
    "k": [0, 1, 2, 3, 4, 5, 6, 7],
    "occupancy": 1,
}
```

并在 configuration 中直接写：

```python
{"config": "3p6 3d9 nl", "required": True}
{"config": "3p6 3d9 mk", "required": False}
```

现在的语义为：

```text
nl -> 使用 DEFAULT_NL["n"] 和 DEFAULT_NL["l"]
mk -> 使用 DEFAULT_NL["m"] 和 DEFAULT_NL["k"]
```

注意 `mk` 不是 FAC 的新语法，而是上游输入文件中的第二套占位符。生成 FAC
输入时仍然展开为普通 FAC configuration，例如：

```text
3p6 3d9 5[s,p,d,f,g]
3p6 3d9 6[s,p,d,f,g,h]
3p6 3d9 7[s,p,d,f,g,h,i]
```

生成器仍会自动过滤不合法角动量：

```text
l <= n - 1
k <= m - 1
```

例如 `m=5, k=7` 不会生成 `5k`。

### Code changes

修改文件：

```text
inputs/target_case_v2.py
inputs/target_case_v2_must_include.py
scripts/generate_fac_input.py
```

主要改动：

```text
inputs/target_case_v2.py
- DEFAULT_NL 增加 m/k 默认范围；
- _normalize_configuration() 现在识别末尾 token 为 nl 或 mk；
- L_SYMBOL_MAP 增加 7 -> "k"。

scripts/generate_fac_input.py
- expand_template() 现在支持 active == "nl" 和 active == "mk"；
- nl 使用 n/l 展开，mk 使用 m/k 展开。

inputs/target_case_v2_must_include.py
- 增加中文标注，说明 required=True/False、DEFAULT_NL、nl/mk 和输出目录后缀。
```

已做检查：

```bash
python3 -m py_compile inputs/target_case_v2.py inputs/target_case_v2_must_include.py scripts/generate_fac_input.py
python3 scripts/generate_fac_input.py inputs/target_case_v2_must_include.py -o /tmp/target_case_v2_must_include_trial.py
```

检查通过。没有实际运行 FAC 或 ODAT-SE。
