"""Editable same-facility diagrams and plots from immutable engineering runs."""
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy

from verify_reserve_delivery import file_sha

COLORS = ['#196b78', '#b66b29', '#765995', '#53825b', '#9b4e65']


def read_run(directory):
    manifest = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
    if manifest['code_identity']['implementation_has_changes'] or manifest['research_trials'] != 0:
        raise ValueError('Figures require clean-source engineering originals')
    for name, identity in manifest['artifacts'].items():
        if file_sha(directory / name) != identity['sha256']:
            raise ValueError('Figure source artifact mismatch: ' + name)
    rows = [json.loads(line) for line in (directory / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
    balances = [json.loads(line) for line in (directory / 'balances.jsonl').read_text(encoding='utf-8').splitlines()]
    scenario = json.loads((directory / 'scenario.json').read_text(encoding='utf-8'))
    return manifest, scenario, rows, balances


def render(package):
    package = Path(package).resolve()
    manifest, scenario, rows, balances = read_run(package / 'combined-episode-CLI')
    normal, _, normal_rows, _ = read_run(package / 'normal-600s')
    p = {row['id']: row['value'] for row in scenario['parameters']}
    times = [row['time_s'] for row in rows]
    output = package / 'figures'
    output.mkdir(exist_ok=False)
    plt.rcParams.update({'svg.fonttype': 'none', 'svg.hashsalt': 'aegisdc-coupled-engineering-v1',
        'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 12,
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True, 'grid.alpha': .15})

    def values(domain, key):
        result = []
        for row in rows:
            value = row['domains'][domain]
            for part in key.split('.'):
                value = value[part]
            result.append(value)
        return result

    def cumulative(key):
        result, total = [0.0], 0.0
        for interval in balances:
            total = math.fsum((total, interval[key]))
            result.append(total)
        return result

    def save(fig, name, details):
        png, svg, receipt = [output / (name + suffix) for suffix in ('.png', '.svg', '.json')]
        fig.savefig(png, dpi=150)
        fig.savefig(svg, metadata={'Date': None})
        plt.close(fig)
        document = dict(schema='aegisdc-coupled-engineering-figure-v1', classification='PRIVATE_ENGINEERING_FIXTURE',
            original_execution_identity=manifest['code_identity'],
            input_runs={name: file_sha(package / name / 'run.json') for name in ('combined-episode-CLI', 'normal-600s')},
            input_artifacts={name: identity['sha256'] for name, identity in manifest['artifacts'].items()},
            plot_script_sha256=file_sha(Path(__file__)), source_units='SI with declared display conversions',
            toolchain=dict(matplotlib=matplotlib.__version__, numpy=numpy.__version__,
                           font='DejaVu Sans', font_file_sha256=file_sha(Path(matplotlib.get_data_path()) / 'fonts/ttf/DejaVuSans.ttf')),
            artifacts={path.name: file_sha(path) for path in (png, svg)}, details=details,
            applicability='Bounded low-order synthetic facility; R134a numerical surrogate; no site calibration or policy gain',
            research_trials=0, model_calls=0, training_calls=0)
        with receipt.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        return document['toolchain']

    fig, axes = plt.subplots(3, 2, figsize=(16, 12), sharex=True)
    fig.subplots_adjust(top=.89, bottom=.11, hspace=.38, wspace=.25)
    axes[0, 0].step(times, values('it_service', 'demand'), where='post', color=COLORS[1], ls='--', label='External demand')
    axes[0, 0].step(times, values('it_service', 'delivered'), where='post', color=COLORS[0], label='Delivered')
    axes[0, 0].set(title='A  One joint compute / network / storage service', ylabel='Service units', ylim=(-.06, 1.35))
    axes[0, 0].legend(fontsize=9, loc='lower right')
    axes[0, 0].text(.02, .08, '275 requested; 231.8 delivered service-unit s\n36 normalized deficit s (a separate integral)',
                    transform=axes[0, 0].transAxes, fontsize=9)
    for name, label, color, style in [('grid_draw_W', 'Grid', COLORS[0], '-'),
            ('generator_output_W', 'Generator', COLORS[1], '--'),
            ('actual_powers_W.compute', 'Actual compute', COLORS[2], '-.')]:
        axes[0, 1].step(times, [value / 1e6 for value in values('power', name)], where='post', label=label, color=color, ls=style)
    axes[0, 1].set(title='B  Finite sources supply actual load', ylabel='MW', ylim=(-.12, 3.2))
    axes[0, 1].legend(fontsize=9, loc='upper left')
    for name, label, color, style in [('lake_pump.volume_flow_m3_s', 'Lake path', COLORS[0], '-'),
            ('internal_pump.volume_flow_m3_s', 'Internal circulation', COLORS[1], '--')]:
        axes[1, 0].step(times, [value * 1000 for value in values('facility_cooling', name)], where='post', label=label, color=color, ls=style)
    axes[1, 0].set(title='C  One paid circulation; primary / backup selection', ylabel='L/s', ylim=(-4, 132))
    axes[1, 0].legend(fontsize=9, loc='lower right')
    for name, label, color, style in [('plate_hx_heat_W', 'Plate HX to lake', COLORS[0], '-'),
            ('condenser_heat_W', 'R134a to water', COLORS[1], '--'),
            ('backup_exchange.heat_W', 'Backup water to air', COLORS[2], '-.')]:
        axes[1, 1].plot(times, [value / 1e6 for value in values('facility_cooling', name)], label=label, color=color, ls=style)
    axes[1, 1].set(title='D  Signed thermal ports; no duplicate HX heat', ylabel='MW')
    axes[1, 1].legend(fontsize=9, loc='lower right')
    for domain, name, label, color, style in [
            ('equipment_environment', 'refrigerant.temperature_K', 'True R134a', COLORS[0], '-'),
            ('facility_cooling', 'hot_temperature_K', 'Hot water', COLORS[1], '--'),
            ('facility_cooling', 'cold_temperature_K', 'Cold water', COLORS[2], '-.'),
            ('equipment_environment', 'room_temperature_K', 'Room air', COLORS[3], ':')]:
        axes[2, 0].plot(times, values(domain, name), label=label, color=color, ls=style)
    valid_report = [d['domains']['control_monitoring']['local_measurement']['temperature_K']
                    if d['domains']['control_monitoring']['local_measurement']['temperature_valid'] else None for d in rows]
    axes[2, 0].plot(times, valid_report, color=COLORS[4], ls=':', lw=1, label='Valid local report')
    axes[2, 0].set(title='E  Physical temperatures and sampled, biased report', ylabel='K')
    axes[2, 0].legend(fontsize=8, ncol=2, loc='upper left')
    for name, initial, label, color, style in [('ups_energy_J', 18000000, 'UPS /18 MJ', COLORS[0], '-'),
            ('fuel_energy_J', 500000000, 'Fuel /500 MJ', COLORS[1], '--'),
            ('starter_energy_J', 100000, 'Starter /100 kJ', COLORS[2], '-.')]:
        axes[2, 1].plot(times, [value / initial for value in values('backup', name)], label=label, color=color, ls=style)
    axes[2, 1].set(title='F  Stores retain separate energy identities', ylabel='Remaining / initial (1)', ylim=(-.02, 1.04))
    axes[2, 1].legend(fontsize=9, loc='lower left')
    for ax in axes.flat:
        ax.set_xlim(0, 240)
        ax.axvspan(65.5, 97.5, color='#e0b9a0', alpha=.15)
        ax.axvline(145.5, color='#65717b', ls=':', lw=.8)
    for ax in axes[-1]:
        ax.set_xlabel('Simulation time /s')
    fig.suptitle('One V6 synthetic facility: coupled engineering response', fontsize=18, fontweight='bold', y=.96)
    fig.text(.5, .92, 'Shading: mains loss until generator transfer. Dotted line: floor water interrupts work. No policy comparison.',
             ha='center', fontsize=11, color='#46545c')
    fig.text(.075, .035, f'Original execution {manifest["code_identity"]["git_commit"][:12]} | '
        'PLC samples every 1 s; reserve actors settle at their declared event times.\n'
        'Normal companion: 600 s, 600 service-unit s delivered, unchanged temperatures and reserve inventories. '
        'Numbers are synthetic assumptions, not Zhengzhou calibration.', fontsize=9, color='#46545c')
    versions = save(fig, 'coupled-response', dict(event_times_s=[10.25, 30.5, 46, 48, 65.5, 65.7, 97.5, 111, 120.5, 145.5, 176, 180],
        normal_duration_s=normal['summary']['duration_s'], normal_delivered_service_unit_s=normal['summary']['delivered_service_unit_s'],
        normal_maximum_temperature_change_K=max(abs(normal_rows[-1]['domains'][d][k] - normal_rows[0]['domains'][d][k])
            for d, k in [('facility_cooling', 'hot_temperature_K'), ('facility_cooling', 'cold_temperature_K'),
                         ('equipment_environment', 'solid_temperature_K'), ('equipment_environment', 'room_temperature_K')])))

    fig, axes = plt.subplots(2, 2, figsize=(16, 10), sharex=True)
    fig.subplots_adjust(top=.88, bottom=.13, hspace=.35, wspace=.24)
    for data, label, color, style in [(cumulative('internal_hot_leaked_mass_kg'), 'Cumulative leak', COLORS[0], '-'),
            (values('space_access', 'floor_water_mass_kg'), 'Floor inventory', COLORS[1], '--'),
            (cumulative('floor_water_drained_mass_kg'), 'Cumulative drainage', COLORS[2], '-.')]:
        axes[0, 0].plot(times, data, label=label, color=color, ls=style)
    axes[0, 0].axhline(10, color='#65717b', ls=':', lw=1, label='Access threshold')
    axes[0, 0].set(title='A  20 kg leaked =8.05 kg retained +11.95 kg drained', ylabel='kg', ylim=(-.5, 22))
    axes[0, 0].legend(fontsize=9, loc='upper left')
    for data, label, color, style in [(cumulative('internal_hot_leak_energy_J'), 'Leak carries in', COLORS[0], '-'),
            (values('space_access', 'floor_water_sensible_energy_J'), 'Retained on floor', COLORS[1], '--'),
            (cumulative('floor_drain_energy_J'), 'Drain carries out', COLORS[2], '-.')]:
        axes[0, 1].plot(times, [value / 1e6 for value in data], label=label, color=color, ls=style)
    axes[0, 1].set(title='B  Internal sensible-energy transfer, not new heat', ylabel='MJ (common cp*T reference)')
    axes[0, 1].legend(fontsize=9, loc='upper left')
    initial_vapor = values('equipment_environment', 'refrigerant.vapor_mass_kg')[0]
    axes[1, 0].plot(times, [value - initial_vapor for value in values('equipment_environment', 'refrigerant.vapor_mass_kg')],
                    color=COLORS[0], label='Vapor gain =liquid loss')
    pressure_axis = axes[1, 0].twinx()
    pressure_axis.plot(times, [value / 1e6 for value in values('equipment_environment', 'refrigerant.pressure_Pa')], color=COLORS[1], ls='--')
    pressure_axis.set_ylabel('R134a saturation pressure /MPa', color=COLORS[1])
    pressure_axis.tick_params(axis='y', colors=COLORS[1])
    axes[1, 0].set(title='C  Fixed-volume phase redistribution; total stays 2000 kg', ylabel='Phase mass change /kg')
    axes[1, 0].legend(fontsize=9, loc='lower left')
    for key, label, color, style in [('worker_travel_person_s', 'Travel /person s', COLORS[0], '-'),
            ('worker_work_person_s', 'Work /person s', COLORS[1], '--'),
            ('tool_occupation_tool_s', 'Tool occupation /tool s', COLORS[2], '-.')]:
        axes[1, 1].plot(times, cumulative(key), label=label, color=color, ls=style)
    axes[1, 1].set(title='D  Real travel, occupation and work interruption', ylabel='Cumulative time by resource')
    axes[1, 1].legend(fontsize=9, loc='upper left')
    axes[1, 1].annotate('120 s travel +25.25 s work\nAbort at145.5 s; tool released', xy=(145.5, 145.25),
                        xytext=(.51, .33), textcoords='axes fraction', fontsize=9,
                        arrowprops={'arrowstyle': '->', 'color': '#65717b'})
    for ax in axes.flat:
        ax.set_xlim(0, 240)
        ax.axvline(145.5, color='#65717b', ls=':', lw=.8)
    for ax in axes[-1]:
        ax.set_xlabel('Simulation time /s')
    fig.suptitle('Inventories and execution retain their own accounts', fontsize=18, fontweight='bold', y=.96)
    fig.text(.5, .92, 'Same saved V6 episode. Work records do not diagnose, repair, create evidence or close a risk issue.', ha='center', fontsize=11)
    fig.text(.075, .04, 'Water uses one zero-K sensible cp*T reference in internal storage, leak, floor mixing and drainage; '
        'carried energy is separate from heat-transfer power.\n'
        f'Original execution {manifest["code_identity"]["git_commit"][:12]}; pure R134a EOS surrogate restricted to 0.1..3 MPa two-phase equilibrium. '
        'Actual site coolant remains unknown.', fontsize=9, color='#46545c')
    save(fig, 'inventory-ledgers', dict(water_reference='common zero-K sensible cp*T; no floor heat exchange, evaporation or condensate',
        leaked_kg=20, drained_kg=11.95, retained_kg=8.05, work_aborted_s=145.5, person_travel_s=120, person_work_s=25.25))

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
        selected_edges.update({identifier: dict(lookup[identifier], graph=graph) for identifier in ids})
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle='-|>', mutation_scale=11, lw=1.4,
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
            (8.3,2.8,'loc_it\nworker_it / IT diagnostic',3.5)]:
        box(ax,x,y,label,width,color)
    edge(ax,'access',['a1'],(2.6,7),(3.9,7),color=color,label='60 s')
    edge(ax,'access',['a5'],(6.1,7),(7.2,7),color=color,label='60 s +electrical qualification')
    edge(ax,'access',['a2'],(5,6.5),(5,5.4),color=color,label='60 s')
    edge(ax,'access',['a3'],(3.2,4.9),(2.6,4.9),color=color,label='120 s')
    edge(ax,'access',['a4'],(5.8,6.5),(8.1,3.3),color=color,label='60 s')
    ax.text(-.3,1.8,'Access to loc_it also requires gate permission, floor water below10 kg and room\n'
        'temperature below the directional work limit. Qualification/tool/shift rules still apply.',fontsize=8,color='#46545c')
    ax.text(.2,.7,'The shared portable flow meter is occupied during travel and work.\n'
        'Arrival, engineering work, diagnosis, repair and verified closure remain different states.',fontsize=9,color='#46545c')
    fig.suptitle('Supported V6 research architecture: four relation semantics, shared entity IDs',fontsize=18,fontweight='bold',y=.96)
    fig.text(.5,.925,'Selected declared edges are expanded by ID in the figure receipt; repeated labels refer to the same V6 entities.',ha='center',fontsize=11)
    fig.text(.065,.035,'Synthetic research facility inspired by Zhengzhou; this is not a site P&ID. '
        'As-built feeders, coolant, hydraulics, staffing and floor plan remain unresolved.\n'
        f'Source configuration SHA256 {file_sha(package / "combined-episode-CLI/scenario.json")[:16]}... | '
        f'Execution {manifest["code_identity"]["git_commit"][:12]} | eight domains retained; no AI/RSI gain.',fontsize=9,color='#46545c')
    save(fig, 'facility-architecture', dict(selected_declared_edges=selected_edges,
        relation_semantics=['physical ports', 'functional/capacity/redundancy', 'control/information', 'personnel access'],
        drawing_rule='Selected edge groups only; shared IDs and capacity/delay/permission conditions are explicit; boxes are editable SVG text and paths'))
    return dict(figures=3, outputs=9, toolchain=versions)
