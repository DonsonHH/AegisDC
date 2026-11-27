"""Editable Office Math from compact MathML expressions used in the article."""
from lxml import etree
from pathlib import Path

def mi(s): return "<mi>"+s+"</mi>"
def mo(s): return "<mo>"+s+"</mo>"
def mn(s): return "<mn>"+s+"</mn>"
def row(*parts): return "<mrow>"+"".join(parts)+"</mrow>"
def sub(a,b): return "<msub>"+a+b+"</msub>"
def frac(a,b): return "<mfrac>"+a+b+"</mfrac>"
def hat(s): return "<mover accent='true'>"+mi(s)+mo("^")+"</mover>"
def summation(lo,hi):return "<munderover>"+mo("∑")+lo+hi+"</munderover>"
def par(x):return row(mo("("),x,mo(")"))
def square(x):return row(mo("["),x,mo("]"))
def under(a,b):return "<munder>"+a+b+"</munder>"
def variable_at(s):return row(mi(s),par(mi("t")))

def expression(key):
    d,y=variable_at("d"),variable_at("y")
    positive=row(d,mo("&gt;"),mn("0"))
    dt=row(mi("d"),mi("t"))
    gap=row(d,mo("−"),y)
    if key=="posterior":
        def product(w):
            arg=par(mi(w))
            return row(sub(mi("b"),mn("0")),arg,*[v for name in "RAIS" for v in (mi(name),arg)])
        return row(mi("b"),par(row(mi("w"),mo("|"),mi("h"))),mo("="),
                   frac(product("w"),row(under(mo("∑"),mi("v")),product("v"))))
    if key=="endpoints":
        return row(mi("L"),mo("="),sub(mo("∫"),positive),frac(gap,d),dt,mo(","),mi("U"),mo("="),mo("∫"),par(gap),dt)
    if key=="objective":
        cost=row(hat("L"),mo("+"),mi("λ"),par(row(sub(hat("T"),mi("staff")),mo("+"),mi("κ"),hat("F"))))
        return row(mi("J"),par(row(mi("π"),mo("|"),mi("h"))),mo("="),sub(mi("E"),mi("b")),square(cost))
    if key=="complexity":
        count=sub(mi("P"),mi("m"))
        prefixes=summation(row(mi("j"),mo("="),mn("0")),mi("m"))
        factorial=frac(row(mi("m"),mo("!")),row(par(row(mi("m"),mo("−"),mi("j"))),mo("!")))
        cost=row(sub(mi("C"),mi("b")),mo("+"),mi("F"),count,par(row(mi("g"),mo("+"),mn("1"))),
                 par(row(sub(mi("C"),mi("cal")),mo("+"),mi("N"),sub(mi("C"),mi("eval")))))
        return row(count,mo("="),prefixes,factorial,mo(","),mi("time"),mo("="),mi("O"),par(cost))
    if key=="inspection":
        mass=sub(mi("μ"),mi("z"))
        summ=under(mo("∑"),row(mi("z"),mo(":"),mass,mo("&gt;"),mn("0")))
        minimum=under(mo("min"),row(mi("σ"),mo("∈"),sub(mi("S"),row(mi("i"),mo(","),mi("z")))))
        def cost(seq,b):return row(mi("C"),par(row(mi("i"),mo(","),seq,mo(","),b)))
        return row(mi("Q"),par(mi("i")),mo("="),par(row(mn("1"),mo("−"),mi("q"))),summ,mass,minimum,
                   cost(mi("σ"),sub(mi("b"),mi("z"))),mo("+"),mi("q"),cost(mo("∅"),mi("b")))
    raise KeyError(key)

def office_math(key):
    ss=Path(r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL")
    xml='<math xmlns="http://www.w3.org/1998/Math/MathML">'+expression(key)+'</math>'
    result=etree.XSLT(etree.parse(str(ss)))(etree.fromstring(xml.encode()))
    return etree.fromstring(etree.tostring(result))
