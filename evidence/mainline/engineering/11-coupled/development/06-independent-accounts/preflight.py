"""DRAFT engineering-tool check; not a frozen capture or research trial."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd()/'scripts'))
from capture_coupled_engineering import configured
from coupled_engineering_checks import check_case
from aegis_dc.plant import simulate_scenario, save_run
from aegis_dc.scenario import load_scenario
root=Path.cwd()
runbook=json.loads((root/'docs/mainline/11-coupled-runbook.json').read_text(encoding='utf-8'))
base=load_scenario(root/runbook['profile'])
output=root/(sys.argv[1] if len(sys.argv)>1 else '.work/coupled-preflight-01')
output.mkdir(parents=True,exist_ok=False)
for item in runbook['cases']:
 scenario=configured(base,item)
 result=simulate_scenario(scenario,duration_s=item['duration_s'],step_s=item['step_s'],boundary_events=item['events'],work_requests=item['work_requests'])
 checks=check_case(item,result,scenario,result['trace'],result['balances'])
 if item['id'] in ('normal-600s','combined-episode-CLI'):
  save_run(result,output/item['id'])
 print(item['id'],json.dumps(checks),flush=True)
from plot_mainline_coupled import render
print('FIGURES',json.dumps(render(output)))
