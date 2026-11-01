"""Single response contract and manually interpreted bounded scalar expressions."""
import ast
import json
import math

from .meta_schema import strict_json
from .multistep_workflow import digest

FEATURES=('risk_delay','deadline_pressure','deadline_peak','travel_cost','freshness_delay')
BASE_EXPRESSION='risk_delay + 0.2*deadline_pressure + 0.05*travel_cost'
CONTRACT={'score_expression':{'type':'string','max_length':256,'example':BASE_EXPRESSION},
          'mechanism':{'type':'string','max_length':700,'example':'Prioritize public risk while accounting for deadlines and travel.'}}


def response_example():return {name:definition['example'] for name,definition in CONTRACT.items()}


def response_contract():
    return {'fields':CONTRACT,'required':list(CONTRACT),'additional_fields':False,
        'feature_names':list(FEATURES),'operators':['+','-','*','min(a,b)','max(a,b)','safe_div(a,b)'],
        'ast_nodes_max':63,'operations_max':24,'constant_abs_max':10,'intermediate_abs_max':1e6,
        'safe_div':'denominator |d|<1e-6 replaced by same-signed1e-6; zero uses positive sign',
        'example':response_example()}


def bounded(value):
    if not math.isfinite(value) or abs(value)>1e6:raise ValueError('Nonfinite or excessive numeric result')
    return float(value)


def operation(name,a,b):
    if name=='add':v=a+b
    elif name=='sub':v=a-b
    elif name=='mul':v=a*b
    elif name=='min':v=min(a,b)
    elif name=='max':v=max(a,b)
    elif name=='safe_div':v=a/(b if abs(b)>=1e-6 else math.copysign(1e-6,b if b else 1.))
    else:raise ValueError('Unregistered operation')
    return bounded(v)


class ScoreExpression:
    def __init__(self,source):
        if type(source) is not str or not 1<=len(source)<=CONTRACT['score_expression']['max_length']:
            raise ValueError('score_expression must be a nonempty string of at most256characters')
        try:tree=ast.parse(source,mode='eval')
        except (SyntaxError,RecursionError) as e:raise ValueError('Expression syntax') from e
        if sum(1 for _ in ast.walk(tree))>63:raise ValueError('AST node limit')
        self.operations=0;self.tree=self._parse(tree.body)
        if self.operations>24:raise ValueError('Operation limit')
        self.variables=self._variables(self.tree)
        if not self.variables:raise ValueError('Expression must depend on public features')
        self.source=source;self.identity=digest(self.tree)

    def _parse(self,node):
        if isinstance(node,ast.Constant):
            if type(node.value) not in (int,float) or not math.isfinite(node.value) or abs(node.value)>10:
                raise ValueError('Only finite constants within10')
            return ('number',float(node.value))
        if isinstance(node,ast.Name):
            if node.id not in FEATURES:raise ValueError('Unknown feature: '+node.id)
            return ('feature',node.id)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            self.operations+=1;x=self._parse(node.operand)
            if isinstance(node.op,ast.UAdd):return x
            return ('number',-x[1]) if x[0]=='number' else ('negative',x)
        if isinstance(node,ast.BinOp) and type(node.op) in (ast.Add,ast.Sub,ast.Mult):
            self.operations+=1;name={ast.Add:'add',ast.Sub:'sub',ast.Mult:'mul'}[type(node.op)]
            a,b=self._parse(node.left),self._parse(node.right)
            if a[0]==b[0]=='number':return ('number',operation(name,a[1],b[1]))
            if name in ('add','sub') and b==('number',0.):return a
            if name=='add' and a==('number',0.):return b
            return (name,a,b)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ('min','max','safe_div') and len(node.args)==2 and not node.keywords:
            self.operations+=1;a,b=(self._parse(x) for x in node.args)
            if a[0]==b[0]=='number':return ('number',operation(node.func.id,a[1],b[1]))
            return (node.func.id,a,b)
        raise ValueError('Only declared scalar arithmetic; no attributes, indexing or arbitrary code')

    @classmethod
    def _variables(cls,node):
        if node[0]=='feature':return {node[1]}
        if node[0]=='number':return set()
        # Detect a constant result without deleting evaluation of its children:
        # an overflowing subtree must still fail even when later multiplied0.
        if node[0]=='mul' and ('number',0.) in node[1:]:return set()
        if node[0]=='sub' and node[1]==node[2]:return set()
        result=set()
        for child in node[1:]:result.update(cls._variables(child))
        return result

    def evaluate(self,features):
        if set(features)!=set(FEATURES) or any(type(v) not in (int,float) or not math.isfinite(v) for v in features.values()):
            raise ValueError('Closed finite public scalar features only')
        def calc(node):
            if node[0]=='number':return node[1]
            if node[0]=='feature':return bounded(features[node[1]])
            if node[0]=='negative':return bounded(-calc(node[1]))
            return operation(node[0],calc(node[1]),calc(node[2]))
        return bounded(calc(self.tree))


def parse_response(raw):
    value=strict_json(raw)
    if not isinstance(value,dict) or set(value)!=set(CONTRACT):raise ValueError('Response must be object with exactly score_expression and mechanism')
    for name,definition in CONTRACT.items():
        if type(value[name]) is not str or not 1<=len(value[name])<=definition['max_length']:
            raise ValueError(name+' must be a nonempty string; not a list/object')
    return ScoreExpression(value['score_expression']),value['mechanism']


def require_mutation(child,parent,seen=()):
    if child.identity==parent.identity or child.identity in seen:raise ValueError('Empty or duplicate canonical expression')
    return child
