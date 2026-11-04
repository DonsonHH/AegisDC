"""Architecture-only visual correction from frozen V6 engineering originals.

The b135 author and all three original figures remain unchanged. This version
uses each selected edge's declared bidirectional field, and moves loc_it so
access edge a4 does not cut through loc_hx. No physical run is performed.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from verify_reserve_delivery import file_sha, git_blob_sha

ROOT = Path(__file__).resolve().parents[1]


def render(package, output, plot_dependencies=None):
    package, output = package.resolve(), output.resolve()
    if output.is_relative_to(package) or not output.is_relative_to(ROOT):
        raise ValueError('Use a new correction directory outside the immutable capture package')
    plot_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    tool_paths = ['scripts/plot_mainline_coupled_architecture_v2.py',
                  'scripts/plot_mainline_coupled.py', 'scripts/verify_reserve_delivery.py']
    tools = {name: file_sha(ROOT / name) for name in tool_paths}
    for name, expected in tools.items():
        if git_blob_sha(ROOT, plot_commit, name) != expected:
            raise ValueError('Commit the exact architecture tools before rendering: ' + name)
    import numpy
    if numpy.__version__ != '2.3.5':
        raise ValueError('Use the pinned project NumPy 2.3.5 before optional plotting dependencies')
    if plot_dependencies:
        sys.path.insert(0, str(plot_dependencies.resolve()))
    from plot_mainline_coupled import read_run, COLORS
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    manifest, scenario, _, _ = read_run(package / 'combined-episode-CLI')
    original = package / 'figures/facility-architecture.json'
    prior = json.loads(original.read_text(encoding='utf-8'))
    for name, expected in prior['artifacts'].items():
        if file_sha(original.parent / name) != expected:
            raise ValueError('The superseded original changed: ' + name)
    output.mkdir(parents=True, exist_ok=False)
    declared = ['declaration.json', 'facility-architecture-v2.png', 'facility-architecture-v2.svg']
    declaration = dict(schema='aegisdc-declared-visual-correction-v1',
        classification='ENGINEERING_VISUAL_SEMANTICS_CORRECTION_ONLY', plot_source_commit=plot_commit,
        declared_artifacts=declared, pinned_authoring_tools=tools,
        original_execution_commit=manifest['code_identity']['git_commit'],
        supersedes=original.relative_to(ROOT).as_posix(), superseded_receipt_sha256=file_sha(original),
        runtime_caches='__pycache__, .pyc and .pyo are not delivered',
        receipt_policy='Separate facility-architecture-v2.json verified against delivery Git bytes')
    (output / 'declaration.json').write_text(json.dumps(declaration, indent=2) + '\n', encoding='utf-8', newline='\n')
    plt.rcParams.update({'svg.fonttype': 'none', 'svg.hashsalt': 'aegisdc-coupled-architecture-v2',
        'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 12})

    def save(fig, name, details):
        png, svg = output / (name + '.png'), output / (name + '.svg')
        fig.savefig(png, dpi=150)
        fig.savefig(svg, metadata={'Date': None})
        plt.close(fig)
        receipt = dict(schema='aegisdc-coupled-architecture-correction-v2',
            classification='ENGINEERING_VISUAL_CORRECTION_NOT_NEW_PHYSICS',
            delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT', plot_source_commit=plot_commit,
            original_execution_identity=manifest['code_identity'],
            source_run=(package / 'combined-episode-CLI/run.json').relative_to(ROOT).as_posix(),
            source_run_sha256=file_sha(package / 'combined-episode-CLI/run.json'),
            source_scenario_sha256=file_sha(package / 'combined-episode-CLI/scenario.json'),
            source_originals={name: identity['sha256'] for name, identity in manifest['artifacts'].items()},
            pinned_authoring_tools=tools, supersedes=declaration['supersedes'],
            superseded_receipt_sha256=file_sha(original),
            superseded_artifacts=prior['artifacts'],
            artifacts={path: file_sha(output / path) for path in declared}, details=details,
            toolchain=dict(matplotlib=matplotlib.__version__, numpy=numpy.__version__, font='DejaVu Sans',
                font_file_sha256=file_sha(Path(matplotlib.get_data_path()) / 'fonts/ttf/DejaVuSans.ttf')),
            physics_rerun=False, full_suite_rerun=False, research_trials=0, model_calls=0, training_calls=0,
            field_calibration='PENDING', research_gain='NOT_ESTABLISHED')
        with (output / (name + '.json')).open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        return receipt

    fig, axes = plt.subplots(2, 2, figsize=(18, 13))
    fig.subplots_adjust(top=.90, bottom=.10, hspace=.22, wspace=.16)
    selected_edges = {}

    def panel(ax, title, color):
        ax.set(xlim=(-.7, 10.7), ylim=(0, 8))
        ax.axis('off')
        ax.set_title(title, loc='left', fontweight='bold', color=color, pad=12)

    def box(ax, x, y, label, width=2.2, color='#196b78'):
        ax.add_patch(FancyBboxPatch((x - width/2, y - .4), width, .8, boxstyle='round,pad=0.06',
                                   edgecolor=color, facecolor='#f7f9fa', lw=1.2, zorder=3))
        ax.text(x, y, label, ha='center', va='center', fontsize=9, zorder=4)

    def edge(ax, graph, ids, start, end, *, color, label='', curve=0):
        lookup = {row['id']: row for row in scenario['graphs'][graph]}
        directions = {bool(lookup[identifier].get('bidirectional', False)) for identifier in ids}
        if len(directions) != 1:
            raise ValueError('An edge group mixes incompatible direction semantics')
        style = '<->' if directions == {True} else '-|>'
        selected_edges.update({identifier: dict(lookup[identifier], graph=graph, rendered_arrowstyle=style) for identifier in ids})
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle=style, mutation_scale=11, lw=1.4,
                     color=color, connectionstyle=f'arc3,rad={curve}', zorder=2))
        if label:
            label_y = start[1] + .62 if start[1] == end[1] else (start[1]+end[1])/2+.17
            ax.text((start[0]+end[0])/2, label_y, label, fontsize=8,
                    color=color, ha='center', va='bottom', zorder=5, bbox=dict(fc='white', ec='none', pad=.5))

    ax = axes[0, 0]; color = COLORS[0]
    panel(ax, '1  Physical: electrical, thermal and fluid ports', color)
    for x, y, label, width in [(1.2,7,'grid',1.6), (4.4,7,'main_switchboard',2.7), (8,7,'load_distribution',2.7),
            (1.2,5.4,'generator',1.8), (8,5.4,'ups',1.5), (4.4,5.4,'rectifier',1.7),
            (1.6,3.8,'compute',2.1), (5.5,3.8,'immersion\n(R134a surrogate)',2.7),
            (8,2.2,'internal_water',2.6), (4.4,2.2,'plate_hx',1.9), (1.2,2.2,'lake',1.6),
            (8,.6,'backup_tower',2.5), (4.4,.6,'reserve_external_air',2.9)]:
        box(ax,x,y,label,width,color)
    for ids, start, end in [(['p_grid'],(2,7),(3,7)), (['p_normal_distribution'],(5.8,7),(6.6,7)),
            (['p_generator'],(1.7,5.8),(3.5,6.6)), (['p_protected_distribution'],(8,5.8),(8,6.6)),
            (['p_rectifier'],(6.7,6.6),(5,5.8)), (['p_compute'],(3.5,5.1),(2,4.2)),
            (['q_compute'],(2.7,3.8),(4.1,3.8)), (['q_condenser'],(6.1,3.4),(7.3,2.6)),
            (['q_internal_hx'],(6.7,2.2),(5.4,2.2)), (['q_to_lake'],(3.4,2.2),(2,2.2)),
            (['q_backup_water'],(8,1.8),(8,1)), (['q_backup_air'],(6.7,.6),(5.9,.6))]:
        edge(ax,'physical',ids,start,end,color=color)
    ax.text(-.4,-.25,'Selected ports: network heats room; storage heats water; circulation/valves remain in V6.\n'
            'HX heat edges are accounting aliases, counted once.',fontsize=8,color='#46545c')

    ax = axes[0, 1]; color = COLORS[1]
    panel(ax, '2  Functional: capacity, common cause and redundancy', color)
    for x,y,label,width in [(2,7,'load_distribution\nshared common cause',3.2), (7.4,7,'critical_service\nmin(demand,C,N,S)',3.4),
            (2,5.3,'rectifier\n5 MW AC limit; eta=.97',3.2), (7.4,5.3,'compute / network / storage\n2 MW /100 kW /100 kW nominal',4.1),
            (2,3.4,'ups\n18 MJ;100 kW output;.2 s',3.3), (7.4,3.4,'local_controller\nintake_pump / internal_pump',3.7),
            (2,1.5,'backup_tower\n1.5 MW heat;2 s switch',3.3), (7.4,1.5,'internal_water\none paid circulation capacity',3.7)]:
        box(ax,x,y,label,width,color)
    edge(ax,'functional',['f_common_distribution'],(3.7,7),(5.6,7),color=color,label='common gate')
    edge(ax,'functional',['f3','f4','f5'],(3.7,5.3),(5.2,5.3),color=color,label='shared input capacity')
    edge(ax,'functional',['f12','f13','f14'],(7.4,5.8),(7.4,6.5),color=color)
    edge(ax,'functional',['f8','f9','f_ups_internal_pump'],(3.7,3.4),(5.4,3.4),color=color,label='auxiliary loads only')
    edge(ax,'functional',['f11'],(3.7,1.5),(5.4,1.5),color=color,label='standby is conditional')
    ax.text(.2,.1,'A path or asset count does not establish capacity. Generator: finite starter/fuel,30+2 s delay;\n'
            'same switchboard/common enclosure. Primary and standby share the internal loop.',fontsize=8,color='#46545c')

    ax = axes[1, 0]; color = COLORS[2]
    panel(ax, '3  Control / information: sampled local protection', color)
    for x,y,label,width in [(2,7,'immersion / internal_pump\nprivate physical states',3.8),
            (7.6,7,'point_temperature\npoint_internal_flow',3.3),
            (7.6,4.9,'local_controller\n1 s clock; biased/invalid reports',3.9),
            (2,4.9,'compute / intake_pump\ninternal_pump / backup_tower',4.0),
            (7.6,2.7,'evidence_inbox\ndeclared graph destination',3.8)]:
        box(ax,x,y,label,width,color)
    edge(ax,'control_information',['c2','c_internal_measurement'],(4,7),(5.9,7),color=color,label='measurement')
    edge(ax,'control_information',['c5','c_internal_local_report'],(7.6,6.5),(7.6,5.4),color=color,label='local report')
    edge(ax,'control_information',['c7','c6','c_internal_command','c_backup_selector'],(5.6,4.9),(4.1,4.9),color=color,label='paid command')
    edge(ax,'control_information',['c9'],(9.4,6.8),(9.3,3.2),color=color,label='graph report',curve=-.3)
    ax.text(.2,1.5,'Local protection continues during supervisory-link loss. A power cycle retains the latch.\n'
        'Hardwired zero-opening pump permits are separate from sampled PLC commands.',fontsize=8,color='#46545c')
    ax.text(.2,.4,'M1 emits private engineering states/work records only. Dispatch and delivered multi-source\n'
        'evidence interfaces remain later tickets; no hidden-state decision oracle is claimed.',fontsize=9,color='#46545c')

    ax = axes[1, 1]; color = COLORS[3]
    panel(ax, '4  Access: independent walking and work feasibility', color)
    for x,y,label,width in [(1.5,7,'loc_entry',2), (5,7,'loc_control',2.1), (8.5,7,'loc_electrical',2.5),
            (5,4.9,'loc_hx\nworker_cooling / flow meter',3.5), (1.5,4.9,'loc_lake',2),
            (8.6,4.9,'loc_it\nworker_it / IT diagnostic',3.1)]:
        box(ax,x,y,label,width,color)
    edge(ax,'access',['a1'],(2.6,7),(3.9,7),color=color,label='60 s')
    edge(ax,'access',['a5'],(6.1,7),(7.2,7),color=color,label='60 s +electrical qualification')
    edge(ax,'access',['a2'],(5,6.5),(5,5.4),color=color,label='60 s')
    edge(ax,'access',['a3'],(3.2,4.9),(2.6,4.9),color=color,label='120 s')
    edge(ax,'access',['a4'],(5.8,6.5),(8.6,5.4),color=color,label='60 s')
    ax.text(-.3,3.2,'Access to loc_it also requires gate permission, floor water below10 kg and room\n'
        'temperature below the directional work limit. Qualification/tool/shift rules still apply.',fontsize=8,color='#46545c')
    ax.text(-.3,1.8,'The shared portable flow meter is occupied during travel and work.\n'
        'Arrival, engineering work, diagnosis, repair and verified closure remain different states.',fontsize=9,color='#46545c')
    fig.suptitle('V6 architecture v2: four relation semantics, shared entity IDs',fontsize=18,fontweight='bold',y=.96)
    fig.text(.5,.925,'Shared IDs refer to the same V6 entities. Access arrowheads follow the actual bidirectional fields.',ha='center',fontsize=11)
    fig.text(.065,.035,'Synthetic research facility inspired by Zhengzhou; this is not a site P&ID. '
        'As-built feeders, coolant, hydraulics, staffing and floor plan remain unresolved.\n'
        f'Source configuration SHA256 {file_sha(package / "combined-episode-CLI/scenario.json")[:16]}... | '
        f'Execution {manifest["code_identity"]["git_commit"][:12]} | Plot source {plot_commit[:12]} | eight domains retained; no AI/RSI gain.',fontsize=9,color='#46545c')
    save(fig, 'facility-architecture-v2', dict(selected_declared_edges=selected_edges,
        relation_semantics=['physical ports', 'functional/capacity/redundancy', 'control/information', 'personnel access'],
        correction='V6 access a1..a5 are bidirectional; arrows now show both heads; a4 avoids loc_hx',
        drawing_rule='Selected edge groups only; shared IDs and capacity/delay/permission conditions are explicit; boxes are editable SVG text and paths'))
    print(json.dumps(dict(status='RENDERED_VISUAL_CORRECTION', plot_source_commit=plot_commit,
        original_execution_commit=manifest['code_identity']['git_commit'],
        output=output.relative_to(ROOT).as_posix(), physics_rerun=False, full_suite_rerun=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plot-dependencies', type=Path)
    arguments = parser.parse_args()
    render(arguments.package, arguments.output, arguments.plot_dependencies)
