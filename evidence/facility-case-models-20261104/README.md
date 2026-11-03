# 三设施资料包的验证记录

阅读入口为[三设施案例包](../../docs/research/20261104/facility-cases/README.md)；单文件HTML包含8幅原创SVG、103条参数记录、28组MathML公式、来源与缺值筛选，复制到空目录仍可离线阅读。

可下载[完整离线资料包](facility-cases-study.zip)，含源码提交`83007944`的阅读稿、SVG、CSV、JSON、来源笔记、工具及验证截图；[bundle-manifest](bundle-manifest.json)记录49个成员和ZIP的SHA。[最终交付复核](../../docs/reviews/facility-cases-20261104.md)逐项对应本轮要求。

|记录|证明范围|
|---|---|
|[reference-inspection.json](reference-inspection.json)|原PDF/作者图/XLSX身份；关键PDF图页的视觉读取；Frontier工作簿Readme、18列表头和前19时间戳的有限检查|
|[build-manifest.json](build-manifest.json)|输入、构建/核对脚本与生成HTML/SVG/CSV的SHA；作者端排版库版本|
|[browser-verification.json](browser-verification.json)|320/390/768/1440/1920宽度、8张原图文字边界、公式渲染、筛选、放大、缩放、Esc/焦点恢复及离线资源请求|

`previews/`保存与浏览器记录匹配的截图，包括8张原图和公式/参数表/手机画面。人工复核确认图内主要文字、箭头语义和公式可读。原始来源媒体继续在本地`.work/facility-cases-20261104/sources`缓存，不重复公开；收据给出来源URL及SHA。

三案例原件复核共发现5项实质问题，均已修正并逐项回查：Frontier设施/设备侧混合焓符号、郑州板换端口与冷容积温度、单组分两相闭合适用条件、兼容PUE口径误标冲突、El Capitan BMS接口终点。复核不把数值口径差异一律当矛盾，也不把发表模型当竣工事实。

验证入口（标准库）：

```bash
python scripts/verify_facility_cases.py
```

重建排版需安装`markdown-it-py`和`latex2mathml`，版本见构建收据；本仓库也兼容已有`.work/paper-writing-deps`：

```bash
python scripts/build_facility_cases.py
```

Windows上的浏览器复核使用Node内置WebSocket和隔离的无界面Chrome：`node scripts/check_facility_cases_browser.cjs`。阅读HTML本身无需这些依赖。

这些核对证明来源边界、文件身份、导出一致和阅读功能；三案例动态方程仍为`UNRESOLVED_CLOSURE`，没有完成现场校准、策略效果评价、训练或新增注册科研实验。旧风险原型和会前资料未改写。
