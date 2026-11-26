"""Typeset English labels on the three accepted vector drawings."""
from pathlib import Path
import re
import subprocess
from lxml import etree as ET

HERE = Path(__file__).resolve().parent
REV = "361574a049f0cfbf816f62af92ff5fd398d77ae8"
ORIGINAL = "docs/mainline/t9-submission-r1/figures/"
SVG = "http://www.w3.org/2000/svg"
NS = {"s": SVG}
PLOTS = ("T7-paired-directions", "T8-edit-tradeoffs")
FACILITY = "facility-information-boundary"

FACILITY_TEXT = {
    "到时证据、合法作业和窗末评价的边界": "Evidence arrival, admissible work and end-of-window evaluation",
    "可到达记录进入在线决策，决策最多发一个请求。执行器检验硬约束后推动耦合设施。只有到达的具名回执或观测返回策略。窗末评价读真实需求与交付，研究后的搜索仅取得本臂已经付费的聚合分。": "The policy receives arrived records and issues at most one request. The executor checks hard limits before acting on the facility. Only delivered observations or receipts return to the policy. The evaluator reads actual demand and delivery. Offline search receives only the aggregate scores paid for by its arm.",
    "在线策略": "Online policy", "仅见公开视图": "Public view only",
    "设施与执行": "Plant and work", "私有真值": "Private state",
    "窗末评价": "Evaluation", "整窗配对": "Full-window pairs",
    "到时证据": "Available evidence",
    "工单、稀疏测点、自己的现场读数": "Orders, sparse sensors, own field readings",
    "核对来源、有效期、执行身份与版本": "Check origin, validity, execution ID and version",
    "决策与首步选择": "Decision and first action",
    "复核义务优先，再比较等待、初检和处置": "Verify obligations first, then compare wait, inspect, act",
    "同一可能读数共用一项后续计划": "Each possible reading has one continuation",
    "实际准入与作业": "Admission and execution",
    "许可、通行、工种、工具、班次、作业窗": "Permit, access, trade, tools, shift and work window",
    "拒绝、无效或未完成均按原样留存": "Keep refusals, invalid actions and unfinished work",
    "耦合设施与本地保护": "Coupled facility and local protection",
    "供电、后备、冷却、计算／网络／存储": "Power, backup, cooling, compute/network/storage",
    "外生扰动、需求与实际服务交付": "Exogenous shocks, demand and actual delivery",
    "评价端独立计量": "Independent evaluation",
    "从需求和实际交付积分服务缺额 L": "Integrate L from demand and actual delivery",
    "工时、费用、违规与有效关闭分列": "Labour, fees, violations and valid closure",
    "离线搜索的反馈范围": "Feedback to offline search",
    "T8 仅用共同父或本臂已付的聚合分": "T8 uses shared-parent or own-arm paid aggregates",
    "程序更新发生在轮间": "Update the program between rounds",
    "更新后验": "Update posterior", "一次请求或暂缓": "One request or defer",
    "合法到达的消息": "Admissible messages received", "执行效果": "Action effect",
    "原生轨迹": "Native trajectory", "聚合回执": "Aggregate receipt",
}
PLOT_TEXT = {
    "合成条件数": "Synthetic conditions", "伦敦式": "London", "荷兰式": "Netherlands",
    "A   全部配对条件": "A   All paired conditions",
    "B   仅 P 原有缺额的条件": "B   Conditions with a deficit under P",
    "缺额较小": "Lower deficit", "缺额相同": "Equal deficit", "缺额归零": "To zero", "仍有缺额": "Still positive",
    "两类合成事故的服务变化": "Service changes in two synthetic incident families",
    "风险策略 V** 与仅保留既有保护的 P 在同一条件内配对": "Risk policy V** and protection-only P, paired within condition",
    "A  两族缺额增加的行数均为 0。B  另有 30 行 P 原本无缺额，V** 新增事件为 0。": "A  Larger deficits occurred on 0 rows in either family. B  In 30 other rows P had no deficit and V** added 0 events.",
    "图示为配对方向和事件转换计数。合成事件率的确认端点 HC 为不可判。": "Counts show paired directions and changes in event status. The confirmatory event-rate endpoint HC was indeterminate.",
    "平均服务缺额差（秒）": "Mean service-deficit difference (s)",
    "平均人员实耗差（人秒）": "Mean labour difference (person-seconds)",
    "16 个已付编辑的服务与工时": "Service and labour for 16 paid edits",
    "每项为 48 条 FIT 条件的均差，方向为候选减共享父。O 与 R 得到同一组编辑。": "Means over 48 FIT conditions, candidate minus shared parent. O and R obtained the same edits.",
    "每四行对应一轮。两臂各支付 16 个候选槽；两臂重合的描述符在图中各列一次。": "Every four rows form a round. Each arm paid for 16 candidate slots. Shared descriptors appear once.",
    "人员列为整板均差。Q3 的 +5 人秒门槛适用于分族单侧上界。": "Labour is a panel mean. Q3 applies the +5 person-second tolerance to each family's one-sided upper bound.",
    "两臂锁定": "Both locked", "另一个降低缺额的编辑": "Other deficit-reducing edit", "其余已付编辑": "Other paid edits",
}

def source(stem):
    return subprocess.check_output(["git", "cat-file", "blob", REV + ":" + ORIGINAL + stem + ".svg"], cwd=HERE)

def parse(raw):
    return ET.fromstring(raw, ET.XMLParser(no_network=True, resolve_entities=False, load_dtd=False))

def original_plot_label(group):
    return "".join(comment.text for comment in group.xpath("./comment()")).strip()

def make_figure(stem):
    root = parse(source(stem))
    if stem == FACILITY:
        for node in root.xpath(".//s:title|.//s:desc|.//s:text", namespaces=NS):
            node.text = FACILITY_TEXT[node.text]
        style = root.find(".//s:style", NS)
        style.text = re.sub(r"font-family:[^;]+;", "font-family:Arial,sans-serif;", style.text)
        style.text = style.text.replace("font-size:15px", "font-size:13.5px").replace("font-size:19px", "font-size:17px")
    else:
        for group in root.xpath("//*[starts-with(@id,'text_')]"):
            original = original_plot_label(group)
            label = PLOT_TEXT[original] if re.search(r"[\u3400-\u9fff]", original) else original
            geometry = group.find("s:g", NS)
            match = re.fullmatch(r"translate\(([-\d.]+) ([-\d.]+)\) scale\(([\d.]+) -[\d.]+\)", geometry.get("transform"))
            x, y, scale = map(float, match.groups())
            size = scale * 100
            anchor = "start"
            if original in ("伦敦式", "荷兰式"):
                x += 27
                size = 7.1
                anchor = "end"
            if original == "合成条件数":
                x += 22.5
                anchor = "middle"
            if original == "平均人员实耗差（人秒）":
                size = 9
                x -= 3
            if original == "另一个降低缺额的编辑":
                size = 7.7
            ink = re.search(r"fill:\s*(#[0-9a-fA-F]+)", geometry.get("style", ""))
            bold = "bold" in original.lower() or any("Bold" in str(u.attrib) for u in geometry.findall("s:use", NS))
            for child in list(group):
                group.remove(child)
            text = ET.SubElement(group, "{"+SVG+"}text", x=f"{x:g}", y=f"{y:g}")
            text.set("font-family", "Arial, sans-serif")
            text.set("font-size", f"{size:g}")
            text.set("text-anchor", anchor)
            if bold:
                text.set("font-weight", "bold")
            if ink:
                text.set("fill", ink[1])
            text.text = label
        for node in root.xpath("//*[local-name()='title']"):
            node.text = "T7 public paired directions and event changes" if stem == PLOTS[0] else "T8 single-edit service deficits and person-seconds"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"

if __name__ == "__main__":
    output = HERE / "figures"
    output.mkdir(exist_ok=True)
    for stem in (FACILITY, *PLOTS):
        (output / (stem + ".svg")).write_bytes(make_figure(stem))
