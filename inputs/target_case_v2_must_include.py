#!/usr/bin/env python3
"""Target input with several configuration templates forced to be included.

Use this when physics intuition says some configurations must be present in
every FAC trial.  The search runner will still enumerate all on/off
combinations of the remaining optional configurations.
"""

import importlib.util
from pathlib import Path


BASE_INPUT = Path(__file__).with_name("target_case_v2.py")


def _load_base_module():
    spec = importlib.util.spec_from_file_location("target_case_v2_base", str(BASE_INPUT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_base_module()


# ===== 修改位置 0：这里定义 nl / mk 的默认展开范围 =====
#
# "3p6 3d9 nl" 会使用 n/l：
#   n = [4, 5, 6, 7]
#   l = [0, 1, 2, 3, 4, 5, 6]
#
# "3p6 3d9 mk" 会使用 m/k：
#   m = [5, 6, 7, 8]
#   k = [0, 1, 2, 3, 4, 5, 6, 7]
#
# generator 会自动过滤掉角动量大于主量子数允许范围的项，例如 m=5 时不会生成 5h。
base.DEFAULT_NL = {
    "n": [4, 5, 6, 7],
    "l": [0, 1, 2, 3, 4, 5, 6],
    "m": [5, 6, 7, 8],
    "k": [0, 1, 2, 3, 4, 5, 6, 7],
    "occupancy": 1,
}


# ===== 修改位置 1：在这里写 configuration，并用 required 标记是否必须包含 =====
#
# 如果你有一个物理猜想，认为某几组 configuration 必须出现在每个 FAC 输入文件中，
# 就把这些项设为 required=True。
#
# 设为 required=False 的项仍然会被 grid_search 做 on/off 枚举。
#
# 如果同一个前缀需要两组不同展开范围，可以写成两个 template：
#   "3p6 3d9 nl" 使用 DEFAULT_NL["n"] / DEFAULT_NL["l"]
#   "3p6 3d9 mk" 使用 DEFAULT_NL["m"] / DEFAULT_NL["k"]
#
#     {
#         "id": "hole_3d9_n4_6_l0_5",
#         "config": "3p6 3d9 nl",
#         "n": [4, 5, 6],
#         "l": [0, 1, 2, 3, 4, 5],
#         "required": True,
#     },
#     {
#         "id": "hole_3d9_m5_7_k0_6",
#         "config": "3p6 3d9 mk",
#         "m": [5, 6, 7],
#         "k": [0, 1, 2, 3, 4, 5, 6],
#         "required": False,
#     },
#
# 注意：如果两组范围有重叠，会生成重复 FAC configuration，例如 5[s,p,d...]
# 可能会在两个 group 中各出现一次。若不想重复，应把范围拆成不重叠。
#
# Any entry with required=True is present in every trial.  Entries with
# required=False are still varied by grid_search.
CONFIGURATIONS = [
    # 必须包含：ground configuration
    {"config": "3p6 3d10", "required": True},

    # 必须包含：根据当前猜想强制加入的 configuration families
    {"config": "3p6 3d9 nl", "required": True},
    {"config": "3p5 3d10 nl", "required": True},

    # 可选：这些 configuration 会继续被搜索程序枚举是否加入
    # 示例：如果需要同前缀的第二套范围，可添加：
    # {"config": "3p6 3d9 mk", "required": False},
    {"config": "3p6 3d8 4s2", "required": False},
    {"config": "3p5 3d9 4s2", "required": False},
]


# ===== 修改位置 1.2：这里控制 OptimizeRadial 的初始组合 =====
#
# 默认继承 base.OPTIMIZE_RADIAL_BASE = "first_required"，即先只用第一组
# required configuration 做 OptimizeRadial，通常就是 ground configuration。
#
# 如果你想从指定组合开始，可以取消注释并写 template id 或自动 shell tag：
#   base.OPTIMIZE_RADIAL_BASE = ["3p6_3d10", "3p6_3d9_nl"]
#   base.OPTIMIZE_RADIAL_BASE = ["4f14"]
#
# 如果确实想恢复旧逻辑，也可以写：
#   base.OPTIMIZE_RADIAL_BASE = "all_required"


# ===== 修改位置 1.5：这里写 configuration 组合之间的物理约束 =====
#
# 搜索程序会自动从 configuration 字符串中提取 shell tag，例如：
#   "4f13 5s1 nl" -> tags include "4f13" and "5s1"
#
# 通用约束已经在 base.SELECTION_CONSTRAINTS 里开启，适用于任意子壳层：
#   - 4f13 + 4f11 会自动要求 4f12；
#   - 4f6 + 4f4 会自动要求 4f5；
#   - 4d10 + 4d8 会自动要求 4d9；
#   - 若某个输入里最高有 4f14，单独出现 4f11 会自动要求至少有 4f12
#     或 4f13 作为桥接。
#
# 下面的 SELECTION_RULES 只用于额外的人工特例；通常保持空列表。
#
# 规则含义：
#   if_any      只要当前组合里出现任意一个 tag/id，就触发规则
#   if_all      当前组合里同时出现所有 tag/id，才触发规则
#   require_any 触发后，必须至少出现其中一个 tag/id
#   require_all 触发后，必须全部出现
SELECTION_RULES = []


# ===== 修改位置 2：这里控制输出目录后缀，避免覆盖原来的 v2 结果 =====
#
# 当前会输出到：
#   runs/search_W46_v2_must_include
#   generated/search_W46_v2_must_include
base.CONFIGURATIONS = CONFIGURATIONS
base.SELECTION_RULES = SELECTION_RULES
base.RUN_NAMING = dict(base.RUN_NAMING)
base.RUN_NAMING["version"] = "v2_must_include"


def build_config():
    return base.build_config()


CONFIG = build_config()
