# 本地 Codex 提问模板

## 1. 项目理解

请先阅读 docs/codex_context.md 和 docs/fac_odatse_framework.md。请总结这个项目中 FAC、ODAT-SE、CRM 分别承担什么角色。

## 2. FAC wrapper

请帮我设计一个 Python wrapper：
- 输入 theta
- 自动生成 FAC input 文件
- 运行 FAC
- 解析能级和跃迁输出
- 返回 line list DataFrame

## 3. 峰团构造

请根据 docs/loss_design.md 写一个函数：

```python
build_peak_groups(line_list, experimental_peaks, energy_shift)
```

要求：
- 使用 Gaussian soft weighting
- 权重为 (2J+1)*A*Gaussian
- 输出每个实验峰对应的 group center 和 potential emission score

## 4. Loss 函数

请写一个适合 ODAT-SE 调用的 loss 函数：

```python
def evaluate_loss(theta):
    ...
    return loss
```

要求：
- FAC 作为 forward solver
- 使用 peak-group evaluation
- anchor peaks 强约束
- ambiguous peaks 弱约束

## 5. ODAT-SE 接入

请帮我设计 ODAT-SE 的输入参数编码方式：
- configuration family id
- mixing switches
- potential strategy
- OptimizeRadial group

并说明哪些参数适合离散搜索，哪些适合连续优化。

## 6. CRM 验证

请帮我设计第二阶段流程：
从 ODAT-SE 得到 top candidates 后，如何自动调用 CRM 生成完整光谱并与实验光谱比较。
