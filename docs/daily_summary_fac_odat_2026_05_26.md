# FAC + ODAT-SE daily summary, 2026-05-26

## Configuration 组合约束：从特例改为通用规则

今天讨论并修正了 configuration family 枚举中的物理约束。

用户指出，之前只写入类似：

```text
4f11 -> 需要 4f13 或 4f12
4f11 + 4f13 -> 需要 4f12
```

这样的特例是不够的。真正需要的是通用规则，能自动适用于任意子壳层，例如：

```text
4f6, 4f5, 4f4
4d10, 4d9, 4d8
3d10, 3d9, 3d8
```

因此今天将组合过滤逻辑改为 shell occupancy 的通用检查。

## 新增通用 shell occupancy 约束

修改文件：

```text
inputs/target_case_v2.py
scripts/run_configuration_search.py
inputs/target_case_v2_must_include.py
```

在 `inputs/target_case_v2.py` 中新增：

```python
SELECTION_CONSTRAINTS = {
    "require_contiguous_shell_occupancies": True,
    "max_shell_hole_depth_without_bridge": 2,
}
```

含义如下。

### 1. 占据数不能跳级

如果同一个子壳层在当前候选组合中同时出现两个占据数，则中间占据数也必须出现。

例如：

```text
4d10 + 4d8  -> 必须有 4d9
4f6  + 4f4  -> 必须有 4f5
3d10 + 3d8  -> 必须有 3d9
```

否则该 configuration set 会在枚举阶段被过滤。

### 2. 深空穴不能孤立出现

相对于输入文件中同一子壳层可见的最高占据数，如果某个候选选中了更深的低占据数，
且差距超过 `max_shell_hole_depth_without_bridge`，则必须同时选入至少一个中间占据数作为桥接。

默认值为：

```text
max_shell_hole_depth_without_bridge = 2
```

因此如果输入空间包含：

```text
4f14
4f13
4f12
4f11
```

则单独出现：

```text
4f14 + 4f11
```

会被过滤，因为中间没有 `4f13` 或 `4f12`。

## 自动 tag 提取

今天还让 `target_case_v2.py` 在 normalize configuration 时自动提取 shell tag。

例如：

```text
4f13 5s1 nl
```

会自动产生：

```text
4f13
5s1
```

这些 tag 会被搜索脚本用于组合合法性判断。

如果未来需要手动补充 tag，也可以在 configuration dict 中显式写：

```python
{"config": "4f13 5s1 nl", "tags": ["custom_tag"], "required": False}
```

## 4f 示例组合数

今天讨论了如下 configuration family：

```text
R1 = 4f14 nl              required
R2 = 4f13 5s2             required
R3 = 4f13 5s1 nl          required

A = 4f13 5p2              optional
B = 4f13 5p1 5l           optional
C = 4f13 5d2              optional
D = 4f12 5s2 5l           optional
E = 4f12 5s1 5p2          optional
F = 4f11 5s2 5p2          optional
```

在前三组 required 的前提下，6 个 optional 原本有：

```text
2^6 = 64
```

个 configuration set。

由于 `F = 4f11 5s2 5p2` 出现时不能缺少 `4f12` 桥接项，因此以下组合被过滤：

```text
R1 R2 R3 + F
R1 R2 R3 + A + F
R1 R2 R3 + B + F
R1 R2 R3 + C + F
R1 R2 R3 + A + B + F
R1 R2 R3 + A + C + F
R1 R2 R3 + B + C + F
R1 R2 R3 + A + B + C + F
```

共 8 个非法组合。

因此合法 configuration set 数为：

```text
64 - 8 = 56
```

## OptimizeRadial 起点修正

今天还修正了 `OPTIMIZE_RADIAL = "auto"` 的语义。

之前 auto baseline 是：

```text
OptimizeRadial on all required configurations
```

用户指出这不合理，因为：

```text
required=True
```

只表示这些 configuration 必须出现在 FAC input 中，不表示一开始就应该全部用于
`OptimizeRadial`。

势优化应该单独定义起点，通常应先从单独基态开始，再尝试加入其他 configuration。

因此今天将默认行为改为：

```text
base_only:
  first required configuration

base_plus_X:
  first required configuration + one other selected template
```

在 `inputs/target_case_v2.py` 中新增：

```python
OPTIMIZE_RADIAL_BASE = "first_required"
```

可选值包括：

```python
OPTIMIZE_RADIAL_BASE = "first_required"
OPTIMIZE_RADIAL_BASE = "all_required"
OPTIMIZE_RADIAL_BASE = ["template_id_a", "template_id_b"]
OPTIMIZE_RADIAL_BASE = ["4f14"]
```

其中列表项可以是 template id，也可以是自动提取的 shell tag。

## 当前 W46 must-include 输入的实际 OptimizeRadial 策略

当前 `inputs/target_case_v2_must_include.py` 中 required 为：

```text
3p6 3d10
3p6 3d9 nl
3p5 3d10 nl
```

但由于 `OPTIMIZE_RADIAL_BASE = "first_required"`，实际 auto 策略变为：

```text
base_only:
  3p6_3d10

base_plus_3p6_3d9_nl:
  3p6_3d10 + 3p6_3d9_nl

base_plus_3p5_3d10_nl:
  3p6_3d10 + 3p5_3d10_nl

base_plus_3p6_3d8_4s2:
  3p6_3d10 + 3p6_3d8_4s2

base_plus_3p5_3d9_4s2:
  3p6_3d10 + 3p5_3d9_4s2
```

这与“先从单独基态开始，再尝试其他势优化组合”的要求一致。

## 验证

今天做了语法检查：

```bash
python3 -m py_compile inputs/target_case_v2.py inputs/target_case_v2_must_include.py scripts/run_configuration_search.py
```

检查通过。

还用临时 configuration set 验证了通用规则：

```text
4f14, 4f13, 4f12, 4f11
  过滤 4f14 + 4f11
  过滤 4f14 + 4f13 + 4f11
  保留 4f14 + 4f13 + 4f12 + 4f11

4f6, 4f5, 4f4
  过滤 4f6 + 4f4

4d10, 4d9, 4d8
  过滤 4d10 + 4d8
```

没有实际运行 FAC 或 ODAT-SE。
