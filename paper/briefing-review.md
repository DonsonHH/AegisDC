# 五屏汇报改版与验证记录

本次从提交`958e777c`的四屏汇报重构，目标是先建立模拟机房情境，再用架构和数据图解释研究。成品为[五屏离线HTML](supervisor-briefing.html)及[口语讲稿](supervisor-talk.md)。主画面采用9张可编辑SVG图，3张原论文图保留为可放大的补充材料。

## 逐屏改动

|屏|核心信息|当前主图|来源与结论边界|
|---|---|---|---|
|1|按时巡检也会错过短时异常|128个机柜和18名仿真巡检员的示意图，及一条实际漏检时间轴|数量取自封存过程与人员记录。机柜17在645秒、885秒检查正常，异常在680—705秒，240秒检查间隔未超过300秒约束。机房示意不代表真实通道布局|
|2|在原巡回中增加经过核算的加查|原固定巡回与新事件响应的并列执行架构|先记待确认任务，检查资格与后续可行性，通过才加查，保留原例行义务。Tour、FIFO与返回证书都在这一屏提供通俗解释|
|3|确认收益和执行成本同时展示|28／70／25的大号柱状图，以及12个过程各自的净增图|三种策略分母均为89段异常，过程配对单位为12个不同种子的主过程。新增45、丢失3、移动+0.50%、完成量−0.33%及相关违规0均沿用封存结果|
|4|后续检查时间改变会有得有失|同一巡检员的机柜17、21简化时间轴|17号是665秒派出的例行访问，685秒才出现其风险，690秒确认；21号比较695秒确认与725秒正常测量。保留完整策略比较的因果边界，不写成一次插入消融|
|5|先交代成果，再确定论文定位|四项成果图，及9条登记规则相对FIFO的确认量点图|先展示机制、条件性证明、实验与初稿。9条规则确认28—60段、FIFO70段，是有限已见开发负结果，模型反馈／RSI独立收益未证明。最后只保留两个讨论问题|

首屏不引入FIFO、返回证书或异常段等缩写／术语。后续分别用“先到先处理”“加查后原任务还来不来得及”“某台设备连续异常的一段时间”解释。讲稿五段正文共772个汉字，另有数字、标点和少量缩写，问答不计入正式汇报。预留时间为45、60、65、75、55秒，总计5分钟；这是汇报安排，不是实测录音时长。

## 当前验证

- `python scripts/build_supervisor_briefing.py`从已有JSON、两份时间线原件和原论文图构建。新图均可编辑，作图输入保留在[briefing-chart-data.json](generated/briefing-chart-data.json)，源文件和输出身份见[manifest](generated/briefing-manifest.json)。重复构建核对成品、作图数据与全部SVG字节身份。
- `node scripts/check_supervisor_briefing.cjs`在Chrome无头浏览器中复制单独一份HTML、禁用网络，检查1366×768和1920×1080下的全部五屏。每屏保留PNG，核对单屏可见、无横向或纵向溢出、图像不越出分配区域、SVG标签不出界／重叠、底部按钮不遮挡。截图另外逐屏查看。
- 14项内容与功能检查覆盖数据图取值、两个讨论问题、案例时间边界、方向键与按钮、数字切至第五屏、首尾按钮、N当前屏讲稿、Q问答与来源、对话框内不误切屏、全屏、第五屏直接链接、9张主图及3张论文原图放大。断网测试没有外部请求或浏览器异常。详见[浏览器验证JSON](generated/briefing-browser-verification.json)。
- 原机制验证包185个文件与搜索包155个文件共340个原件的SHA均匹配原索引。主论文、主结果、研究代码与协议未修改；本次新环境评价、研究模型调用及训练均为0。
- 改版前的HTML、讲稿、模板、构建脚本和manifest按原Git对象逐字节保留，见[旧版入口](briefing-history/958e777c/supervisor-briefing.html)及[归档身份](briefing-history/958e777c/baseline.json)。

## 截图

|画面|1366×768|1920×1080|
|---|---|---|
|场景与漏检|[查看](generated/briefing-previews/1366x768-screen-1.png)|[查看](generated/briefing-previews/1920x1080-screen-1.png)|
|执行架构|[查看](generated/briefing-previews/1366x768-screen-2.png)|[查看](generated/briefing-previews/1920x1080-screen-2.png)|
|数据结果|[查看](generated/briefing-previews/1366x768-screen-3.png)|[查看](generated/briefing-previews/1920x1080-screen-3.png)|
|案例时间轴|[查看](generated/briefing-previews/1366x768-screen-4.png)|[查看](generated/briefing-previews/1920x1080-screen-4.png)|
|成果与讨论|[查看](generated/briefing-previews/1366x768-screen-5.png)|[查看](generated/briefing-previews/1920x1080-screen-5.png)|
