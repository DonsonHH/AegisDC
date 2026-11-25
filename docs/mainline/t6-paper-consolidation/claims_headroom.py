"""C4 evidence only. Its claim text remains unfilled until the user's decision."""
from fractions import Fraction as F
from claims_sources import BASE,OLD,NEW,PDESIGN,POLD,PNEW,P1,mean,require,roster


def build(book):
    m54,m58=roster(book);data=book.get(OLD,POLD);old=data["conditions"];new=book.get(NEW,PNEW)["conditions"]
    accepted=book.get(BASE,P1)["C4"];main="MAIN-R-3";second="Q22"
    require(len({r["key"] for r in old})==len(old)==36 and len({r["key"] for r in new})==len(new)==36,"C4 full two boards")
    for r in old+new:
        cert=r["minimum"] if "minimum" in r else r["lower"]
        require(cert["status"]=="ATTAINED" and cert["actual_chain"] and cert["native_L"]==r["arms"]["ORACLE"]["L"]==cert["certified_min"],
                "certified attained original bound "+r["key"])
    require(all(r["arms"]["W"]["entry"]["actual"]==main for r in new),"new W frozen identity")
    vals=[]
    def add(id,label,unit,rev,path,fields,op="value",rows=None,**kw):
        m=book.num("C4."+id,label,unit,rev,path,fields,op,rows,**kw);vals.append(m);return m["id"],F(m["exact"])
    oldids=list(range(len(old)));newids=list(range(len(new)))
    root="/conditions/{i}";bound=root+"/minimum/certified_min";newbound=root+"/lower/certified_min"
    def lv(role):return root+"/arms/"+role+"/L"
    rosters={};best_ids=[];second_ids=[];post_ids=[];room_ids=[]
    for title,roles in (("fixed54",m54),("replay58",m58)):
        # Rank by the full-window mean above the original bound before choosing a single member.
        scores={l:mean([F(r["arms"][l]["L"])-F(r["minimum"]["certified_min"]) for r in old]) for l in roles}
        order=sorted(roles,key=lambda l:scores[l])
        require(order[:2]==[main,second] and scores[second]<scores[order[2]],"ordered top two fixed policies")
        fields=[lv(l) for l in roles]
        n,_=add(title+".n","候选集合成员数","项",BASE,P1,["/C4/pools/"+title+"/members"],"length")
        b,bv=add(title+".best","单一固定向量最小整板平均剩余","秒",OLD,POLD,[bound,*fields],"fixed_best",oldids)
        s,sv=add(title+".second","单一固定向量第二整板平均剩余","秒",OLD,POLD,[bound,*fields],"fixed_second",oldids)
        post,pv=add(title+".posthoc","逐条件事后择优的平均剩余；非可部署","秒",OLD,POLD,[bound,*fields],"rowwise_best_gap",oldids)
        h,hv=add(title+".conditional_room","最佳固定向量至逐行事后最低的条件化余量","秒",OLD,POLD,[lv(main),*fields],"mean_delta",oldids)
        require(bv==scores[main] and sv==scores[second] and hv==bv-pv and all(min(F(r["arms"][l]["L"]) for l in roles)==F(r["minimum"]["certified_min"]) for r in old),
                "rowwise witness and locked policy are separate")
        require(F(accepted["pools"][title]["fixed_vector_panel_means"][main]["fraction"])==bv and
                F(accepted["pools"][title]["fixed_vector_panel_means"][second]["fraction"])==sv,"stage 1 ranking cross-check")
        rosters[title]=dict(members=roles,member_count=n,first=order[0],runner_up=order[1],fixed_first_gap=b,fixed_second_gap=s,
                            retrospective_gap=post,conditional_room=h,full_order=order)
        best_ids.append(b);second_ids.append(s);post_ids.append(post);room_ids.append(h)
    old_n,_=add("old.n","v3a 条件分母","条",OLD,POLD,["/conditions"],"length")
    new_n,_=add("new.n","新面板条件分母","条",NEW,PNEW,["/conditions"],"length")
    threshold,_=add("threshold","贴界容差","秒",BASE,P1,["/C4/tolerance_s"])
    anchors={}
    for l in (main,second):
        key,v=add("old."+l+".observed",l+" 的实际全板平均剩余","秒",OLD,POLD,[lv(l),bound],"mean_delta",oldids);anchors[l]=key
    old_hits,iv=add("old.attained","旧板 MAIN-R-3 贴界条件","条",OLD,POLD,[lv(main),bound],"at_bound",oldids,tolerance="1/100")
    old_room,ov=add("old.above","旧板 MAIN-R-3 有余量的条件","条",OLD,POLD,[lv(main),bound],"above_tolerance",oldids,tolerance="1/100")
    hits,nv=add("new.attained","新板 W 贴界条件","条",NEW,PNEW,[lv("W"),newbound],"at_bound",newids,tolerance="1/100")
    remaining,rv=add("new.room","新板相同权限下相对 W 尚余的平均条件化改善上限","秒",NEW,PNEW,[lv("W"),newbound],"mean_delta",newids)
    require(iv+ov==len(old) and nv==len(new) and rv==0,"old/new separate actual headroom")
    examples=[]
    for i,r in enumerate(old):
        gap=F(r["arms"][main]["L"])-F(r["minimum"]["certified_min"])
        if gap<=F(1,100):continue
        lower=r["minimum"]["certified_min"];w=next(l for l in m54 if r["arms"][l]["L"]==lower)
        prefix=f"/conditions/{i}";kid=r["key"]
        rid,v=add("old.room."+kid,"MAIN-R-3 高于下界的逐行余量","秒",OLD,POLD,[prefix+"/arms/"+main+"/L",prefix+"/minimum/certified_min"],"subtract")
        wid,_=add("old.offline_witness."+kid,"事后可达界候选在该行的剩余","秒",OLD,POLD,[prefix+"/arms/"+w+"/L",prefix+"/minimum/certified_min"],"subtract")
        examples.append(dict(id="C4.room."+kid,key=kid,panel="v3a",level="开发",family=r["family"],metrics=[rid,wid],retrospective_witness=w,
                             limitation="此行反驳旧板固定向量全板无余量；见证的选择使用事后成绩。",
                             source=book.ref(OLD,POLD,prefix)))
    return dict(id="C4",statement="",level=["开发","确认"],status="未建立",comparator="旧板最佳固定 MAIN-R-3 与固定候选池的事后逐行最低；新板 W 与认证全知下界。没有同预算 RSI 处理。",
        denominator={"v3a":old_n,"v3c":new_n,"candidate_sets":[rosters[s]["member_count"] for s in rosters]},
        numbers=vals,sections=[
            dict(id="C4.a",level="开发",reading="全板只能用同一候选时，两种名册均由 MAIN-R-3 居首、Q22 居次。两者的平均剩余分别为 82.03 秒和 86.67 秒。",
                 metric_ids=[*best_ids,*second_ids,anchors[main],anchors[second]],roster_ref="pools"),
            dict(id="C4.b",level="开发",reading="事后信息，非可部署策略。各条件可以选不同向量，平均剩余为 0.00 秒；旧板相对最佳固定向量有 82.03 秒的条件化余量。没有证据说明决策时可取得这部分余量。",
                 metric_ids=[*post_ids,*room_ids,old_hits,old_room,threshold],label="事后信息，非可部署策略"),
            dict(id="C4.c",level="确认面板中的描述性读回",panel_level="确认",reading="新板实际使用的 W 是 MAIN-R-3。36/36 条都达到有原生见证的下界，实际平均剩余为零，故本板相对 W 的服务缺额条件化余量为 0。",
                 metric_ids=[new_n,hits,remaining,threshold],scope="同一新板、同一服务端点、同一合法动作条件")],
        pools=rosters,
        named_roster_evidence=[book.ref(OLD,PDESIGN,"/roles/random"),book.ref(OLD,PDESIGN,"/roles/reference"),book.ref(BASE,P1,"/C4/only_in_58")],
        failure_conditions=[
            dict(condition="旧板、已知条件逐行选优不能替换整板固定策略；剩余不为零的具体条件保存在反例表。",
                 metrics=[old_n,old_hits,old_room,*room_ids]),
            dict(condition="新板 W 贴界只限制该板服务缺额终点上的改进空间。新旧面板不合并，不据此断言 RSI 无用、普遍不可辨识或存在已实现的增量。",
                 metrics=[hits,remaining])],counterexamples=examples,
        wording_owner="用户裁决；本阶段 statement 留空。")
