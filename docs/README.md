# FAC + ODAT-SE 本地 Codex 提问资料包

这个资料包用于在本地 Codex 中持续提问和开发代码。核心目标是：

> 用 FAC 作为 forward solver，计算给定 configuration/potential 下的能级、跃迁能量和 A-value；
> 用 ODAT-SE 作为 inverse solver，在 configuration 与 potential 空间中搜索最能解释 EBIT 实验 UTA 峰团的原子模型；
> 最后只对筛选出的候选模型再进行 CRM 和完整光谱验证。

建议在本地项目中放置结构：

```text
project/
  docs/
    README.md
    fac_odatse_framework.md
    codex_context.md
    loss_design.md
    workflow.md
    questions_for_codex.md
    short_prompt.txt
```

使用 Codex 时，可以先让它读取 `docs/codex_context.md`，再针对具体程序开发提问。
