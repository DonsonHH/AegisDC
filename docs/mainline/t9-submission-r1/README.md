# 维护降级时，何时值得等待一次付费核查？

[投稿修订稿（PDF）](manuscript.pdf) · [网页阅读](manuscript.html) · [可编辑正文](manuscript.md) · [版本与证据](evidence.md)

本版从已验收的 [T9 正文](../t9-paper-final/manuscript.md) 派生，沿用 `28c59691` 的四项主张。C1 先报告同方法允许／禁用自选初检的差值，再报告整套方法差。原 H1→H2→H3 的顺序检验不变。稿内的 T8 工时表分别列出 FIT 实测均差与 38 块条件预测。

图 1 给出设施、在线视图和评价端的边界。图 2、图 3 在 PDF 主文中直接使用原先审阅的矢量 PDF 内容流与字体。对应的 [T7 矢量图](figures/T7-paired-directions.pdf) 和 [T8 矢量图](figures/T8-edit-tradeoffs.pdf) 也可单独取用。

从本目录运行以下命令可只读核对正文、结果表、矢量内容和实际实现的冻结身份。核验读取公开材料，使用 Python、Beautiful Soup 及 pypdf，本机还须可运行 Git。

```text
python -B verify.py --check --checkout-bytes
```

需要重新排印时，`python -B render.py --output-dir <新的输出目录>` 将同一份 Markdown 生成 HTML 和 PDF。排印使用 markdown-it-py、Beautiful Soup、Playwright、Chrome 或 Chromium 和 pypdf，中文显示需中文字体。可用 `--browser-executable` 指定已有浏览器的执行文件。结果图的 SVG 可由 `render_figures.py <研究仓库根目录>` 用已发布的两张汇总表导出。论文撰写未调用设施、评分器或 Slurm，也未读取 DEV 面板或 H2/H3 封存材料。
