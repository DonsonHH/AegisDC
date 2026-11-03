"""Editable architecture drawings for the implemented supplemental models."""
from briefing_diagrams import BLUE, GOLD, INK, MUTED, TEAL, line, rect, svg, text
from report_diagrams import arrow


def box(x, y, width, heading, sub, color=BLUE, height=78):
    return [rect(x, y, width, height, '#f2f6f9', rx=3), text(x+width/2, y+29, heading, 23, color, 'middle', 600),
            text(x+width/2, y+60, sub, 20, MUTED, 'middle')]


def conditional_unet():
    p = [text(20, 34, '已训练的物理残差 conditional VAE-U-Net', 29, BLUE, weight=650),
         text(20, 69, '8×16离散设备网格 · 295,777个参数 · 四个连续5秒端点 · 在线使用条件先验均值', 21, MUTED)]
    p += box(20, 105, 185, '公开历史输入', '4×14＋名义T̂')
    p += box(255, 105, 165, '编码器①', '8×16×16')
    p += box(465, 205, 165, '编码器②', '4×8×32')
    p += box(675, 305, 165, '瓶颈', '2×4×64')
    p += box(885, 205, 165, '解码器②', '4×8×32')
    p += box(1095, 105, 165, '解码器①', '8×16×16')
    p += [arrow(210, 145, 245, 145), arrow(420, 180, 455, 218), arrow(630, 280, 665, 318),
          arrow(845, 328, 875, 278), arrow(1055, 218, 1085, 178),
          arrow(425, 143, 1085, 143, TEAL), text(750, 132, '空间跳接①', 20, TEAL, 'middle'),
          arrow(635, 243, 875, 243, TEAL), text(752, 233, '跳接②', 20, TEAL, 'middle')]
    p += box(675, 435, 240, '条件先验 p(z|x)', '16维潜变量；在线取μ', TEAL)
    p += [arrow(755, 389, 755, 425, TEAL),
          '<path d="M915,475 H960 V355" fill="none" stroke="#147469" stroke-width="2"/>',arrow(960,355,845,355,TEAL),
          text(970, 408, '潜变量融合', 20, TEAL)]
    p += box(1095, 305, 165, '1×1输出头', '温度残差 ΔT̂')
    p += [arrow(1178, 188, 1178, 295), arrow(1178, 388, 1178, 425)]
    p += box(1020, 435, 240, '名义估计＋残差', '新鲜量测统一覆盖', BLUE)
    p += [rect(20, 340, 555, 180, '#fbf6ec', rx=3), text(40, 375, '仅训练：条件后验 q(z|x,T真实)', 23, GOLD, weight=600),
          text(40, 414, '以物理温度作监督目标；重建损失＋条件KL', 21, MUTED),
          text(40, 452, '测试与在线推理只接收公开历史 x', 21, MUTED),
          text(40, 490, '开发集选各种子checkpoint，测试前锁定SHA', 21, MUTED),
          line(580,474,665,474,GOLD,2,**{'stroke-dasharray':'5 5'}),text(620,460,'KL对齐',19,GOLD,'middle'),
          text(20, 575, '输入、名义估计与新鲜量测属于公开观测；事后温度只用于训练监督和离线评价。', 21, MUTED)]
    return svg('supplement-unet', 1280, 605, '温度残差CVAE-U-Net实际结构与信息边界', '两个空间下采样及上采样层，条件先验与训练后验，名义温度残差及共同新鲜量测校正。', p)


def shared_decision():
    p = [text(20, 34, '估计器与调度器交叉比较，共用同一执行约束', 29, BLUE, weight=650)]
    p += box(20, 90, 265, '公开遥测与已完成测量', '名义估计或CVAE估计')
    p += box(365, 90, 260, '共同候选生成', '例行下一项＋本人待办')
    p += box(705, 90, 250, '共同可行性筛选', '资格／预约／返回／预算')
    p += [arrow(290, 130, 355, 130), arrow(630, 130, 695, 130)]
    p += box(70, 255, 260, 'FIFO / Greedy', '同一公开队列与风险')
    p += box(425, 255, 350, '共享PPO：21维候选特征', '32→32→1；合法集合内选择')
    p += box(870, 255, 330, '批准选择并执行量测', '固定执行者顺序；逐条记账')
    p += ['<path d="M830,173 V218 H200 V245" fill="none" stroke="#526675" stroke-width="2"/>',
          '<path d="M830,218 H600 V245" fill="none" stroke="#526675" stroke-width="2"/>',
          '<path d="M330,295 H365 V365 H840 V295 H860" fill="none" stroke="#526675" stroke-width="2"/>',
          arrow(780, 295, 860, 295),
          '<path d="M1040,338 V395 H35 V190 H150" fill="none" stroke="#147469" stroke-width="2"/>',arrow(150,190,150,173,TEAL),
          text(650, 425, '测量更新公开状态，再产生风险请求与下一轮候选', 22, TEAL, 'middle')]
    p += [rect(20, 470, 1200, 105, '#fbf6ec', rx=3),
          text(40, 505, '仅训练：10维公开全局特征→critic；每359步完整回合更新PPO', 23, GOLD, weight=600),
          text(40, 547, '真实异常标签用于离线确认、等待和误差评价；策略奖励沿用公开观测函数。', 21, MUTED),
          text(20, 620, '每种估计条件训练3个种子×120回合；测试前锁定六个策略。Tour只执行原定循环。', 21, MUTED)]
    return svg('supplement-crossed-design', 1280, 650, '同信息同约束的估计器和调度器交叉设计', '两种估计器共享候选生成，FIFO、Greedy及共享PPO在同一合法候选集合内决策；物理真值只离线评分。', p)


def build():
    return {'supplement-unet': conditional_unet(), 'supplement-crossed-design': shared_decision()}
