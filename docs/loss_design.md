# 峰团评价与 Loss 设计

## 1. 实验峰不是单线

实验峰 k 具有：

- 中心能量 E_k^ex
- 标准差 sigma_k 或 FWHM
- 峰面积或峰高

理论 FAC 输出许多离散跃迁线，每条线 i 有：

- E_i^cal
- A_i
- J_u,i

## 2. 理论线团

对每个实验峰 k，定义理论线团 G_k。

推荐不要使用硬窗口，而使用高斯软权重：

```text
w_i,k = (2J_u,i + 1) A_i exp[-(E_i^cal + E_shift - E_k^ex)^2 / (2 sigma_k^2)]
```

其中：

- (2J+1)A 表示辐射潜力
- Gaussian 因子表示实验峰宽约束
- E_shift 表示整体能量 shift

## 3. 线团中心

```text
E_k^grp = sum_i(w_i,k E_i^cal) / sum_i(w_i,k)
```

## 4. 线团辐射潜力

```text
S_k^grp = sum_i w_i,k
```

注意：S_k^grp 不是真实强度，只是 potential emission score。

## 5. 全局 shift

多个实验峰应尽量共享同一个 shift：

```text
delta_k = E_k^ex - E_k^grp
E_shift = average(delta_k)
r_k = E_k^ex - (E_k^grp + E_shift)
```

## 6. 简化 loss

```text
L = w1 * sum_k(r_k^2)
    - w2 * sum_k(log(S_k^grp + epsilon))
    + w3 * P_missing
    + w4 * P_unstable
```

## 7. Anchor peaks 与 Ambiguous peaks

### Anchor peaks

用于强约束：

- 峰附近结构简单
- 强线主导明确
- 可用于确定 global shift

### Ambiguous peaks

用于弱约束：

- 附近候选线团复杂
- A 大的线可能因 population 小而不形成峰
- 最终归属必须由 CRM 决定

可以写成：

```text
L_total = L_anchor + alpha * L_ambiguous
```

其中 alpha < 1。
