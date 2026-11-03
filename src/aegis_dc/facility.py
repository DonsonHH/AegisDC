"""Separate facility service relationships from personnel access relationships."""
import math
from pathlib import Path
from patrol_rsi.contracts import strict_json

DEPENDENCY_KINDS={'power','cooling','control','data','service'}


def load_model(path):
    model=strict_json(Path(path).read_text(encoding='utf-8'))
    if model.get('schema')!='aegisdc-facility-structure-v1':raise ValueError('Unknown facility schema')
    if model.get('basis')!='illustrative_composite_not_as_built':raise ValueError('Declare the structural model basis')
    zones={row['id'] for row in model['zones']};assets={row['id']:row for row in model['assets']}
    if len(zones)!=len(model['zones']) or len(assets)!=len(model['assets']):raise ValueError('Duplicate zone or asset')
    sources=model['sources']
    for asset in assets.values():
        if asset['zone'] not in zones:raise ValueError('Asset has unknown zone')
        if asset['evidence_status'] not in {'reference_supported','candidate_not_site_verified'}:raise ValueError('Unknown asset evidence status')
        if asset['evidence_status']=='reference_supported' and not asset['source_refs']:raise ValueError('Supported asset needs a source')
        if any(ref not in sources for ref in asset['source_refs']):raise ValueError('Unknown source reference')
    for edge in model['service_dependencies']:
        if edge['from'] not in assets or edge['to'] not in assets or edge['kind'] not in DEPENDENCY_KINDS:
            raise ValueError('Invalid service dependency')
        if edge['basis']!='model_proposal':raise ValueError('Dependency mapping is not a verified site drawing')
    for edge in model['walking_links']:
        if edge['from'] not in zones or edge['to'] not in zones:raise ValueError('Walking links use zones, not asset dependencies')
        minutes=edge['minutes']
        if type(minutes) not in (int,float) or not math.isfinite(minutes) or minutes<=0:raise ValueError('Invalid assumed walking time')
        if edge['basis']!='synthetic_assumption':raise ValueError('Declare walking assumptions')
    if any(asset not in assets for asset in model.get('fixed_sensor_assets',[])):raise ValueError('Unknown fixed sensor target')
    return model


def candidate_service_exposure(model,asset_id):
    """Reachability screens possible exposure, not outage probability or a cut-set proof."""
    assets={row['id']:row for row in model['assets']}
    if asset_id not in assets:raise ValueError('Unknown asset')
    reached={asset_id};pending=[asset_id]
    while pending:
        current=pending.pop()
        for edge in model['service_dependencies']:
            if edge['from']==current and edge['to'] not in reached:
                reached.add(edge['to']);pending.append(edge['to'])
    return sorted(asset for asset in reached if assets[asset]['kind']=='service')


def describe(model):
    return {'status':'STRUCTURE_DEFINED_PARAMETERS_PENDING','basis':model['basis'],
            'zones':len(model['zones']),'assets':len(model['assets']),
            'service_dependencies':len(model['service_dependencies']),'walking_links':len(model['walking_links']),
            'fixed_sensor_targets':len(model.get('fixed_sensor_assets',[])),
            'unknown_parameters':model['parameter_gaps'],
            'exposure_meaning':'possible service exposure by declared edges; not a calibrated failure model',
            'default_fixed_tour':False,'requires_full_realtime_telemetry':False}
