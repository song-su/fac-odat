# 推荐工作流程

## Phase 1: FAC + ODAT-SE 快速反演

1. 从实验谱中拟合峰：
   - peak center
   - sigma 或 FWHM
   - peak area

2. 人工准备 configuration family：
   - core
   - core + mixing
   - core + decorating

3. ODAT-SE 生成参数 theta：
   - configuration family id
   - mixing switch
   - OptimizeRadial group
   - potential strategy

4. 根据 theta 自动生成 FAC input。

5. 运行 FAC，得到能级和跃迁表。

6. 对每个实验峰构造理论线团。

7. 计算：
   - line-group center
   - potential emission score
   - global shift consistency

8. 返回 loss 给 ODAT-SE。

9. ODAT-SE 搜索最优 configuration/potential。

## Phase 2: 简单卷积验证

对 top candidates：

- 使用 FAC line list
- 简单 Gaussian convolution
- 比较峰中心、峰宽、肩结构、峰间距

## Phase 3: CRM 完整验证

对最终少数候选：

- 计算 population
- 计算 emissivity
- 加入 ion abundance
- 生成完整 synthetic spectrum
- 与实验光谱比较
