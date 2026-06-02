# FAC + ODAT-SE 方法框架

## 1. 总体框架

```text
Experiment spectrum
        ↓
     ODAT-SE
        ↓
(configuration + potential)
        ↓
        FAC
 (Energy / A-value / J)
        ↓
 Peak-group evaluation
        ↓
    loss function
        ↓
    optimization
        ↓
 Best atomic model
        ↓
        CRM
        ↓
 Full spectrum
        ↓
 Compare with experiment
```

## 2. FAC 的角色

FAC 是 forward solver。给定一组参数：

- configuration set
- CI structure
- radial potential
- OptimizeRadial strategy

FAC 输出：

- energy levels
- transition energies
- A-values
- J values
- line list

## 3. ODAT-SE 的角色

ODAT-SE 是 inverse solver。它不断提出新的模型参数 theta：

```text
theta = {configuration family, mixing switches, potential strategy, radial optimization group}
```

每次 theta 都被送入 FAC 计算，然后根据实验峰团特征计算 loss。

ODAT-SE 的目标是：

```text
theta* = argmin L(theta)
```

## 4. CRM 的角色

CRM 不参与第一阶段大规模搜索，只用于少数候选模型的最终验证。

CRM 决定：

- population
- cascade
- metastable contribution
- ion abundance
- final emissivity
- full synthetic spectrum
