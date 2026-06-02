# Codex 项目上下文：FAC + ODAT-SE 原子光谱反演

## 研究背景

已有 EBIT 实验光谱。目标是用 FAC 与 CRM 模拟高电荷态重元素离子的 UTA 光谱。

完整 FAC + CRM 光谱计算成本较高，因此第一阶段不直接拟合完整光谱，而是仅使用 FAC 输出的：

- 能级
- 跃迁能量
- A-value
- 上下能级 J 值

来构造实验峰附近的理论线团，并用 ODAT-SE 搜索最合适的 configuration 与 radial potential / OptimizeRadial 策略。

## 核心思想

FAC 解决顺问题：

```text
configuration + potential -> FAC -> energy levels + transition energies + A-values
```

ODAT-SE 解决逆问题：

```text
experimental peak features -> search configuration + potential
```

## 重要限制

实验峰是 UTA / blended peak，不是单条线。因此不能假设：

```text
one experimental peak = one theoretical transition
```

而应采用：

```text
one experimental peak = one theoretical line group
```

## 第一阶段评价目标

第一阶段不是判断真实实验强度，也不是完整谱拟合，而是判断某组 configuration/potential 是否能在实验峰附近产生合理的候选线团。

真实强度需要 CRM，因为：

```text
I_ul ∝ N_u A_ul
```

FAC 阶段只有 A-value，没有 population。因此 A-value 只能作为“辐射潜力”，不能等同于真实峰强。
