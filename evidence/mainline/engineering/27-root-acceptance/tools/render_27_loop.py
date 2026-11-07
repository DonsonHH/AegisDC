"""Render audited ticket 27 saved observations; never import the simulator."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import matplotlib as mpl

mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


NAVY = '#162b3c'
MUTED = '#4a6574'
TEAL = '#087a76'
BLUE = '#2c5fbb'
ORANGE = '#b95021'
GRAY = '#d6e0e6'
PURPLE = '#71528e'
CREAM = '#f7f9fb'


def read(path):
    return json.loads(path.read_bytes())


def hash_file(path):
    return sha256(path.read_bytes()).hexdigest()


def common(title, subtitle, size):
    figure = plt.figure(figsize=size, facecolor='white')
    figure.text(.08, .955, title, color=NAVY, fontsize=21, fontweight='bold', va='top')
    figure.text(.08, .906, subtitle, color=MUTED, fontsize=10.5, va='top')
    return figure


def chronology(trace, run, checks):
    figure = common('One facility, one closed loop',
                    'Ticket 27  /  Saved 10 s engineering trajectory  /  Synthetic, not an effect comparison', (12, 9))
    grid = figure.add_gridspec(4, 1, top=.856, bottom=.145, left=.225, right=.935, hspace=.45,
                              height_ratios=[1, 1, .8, 1.4])
    ax = [figure.add_subplot(grid[0])]
    ax += [figure.add_subplot(grid[i], sharex=ax[0]) for i in range(1, 4)]
    times = [row['time_s'] for row in trace]
    domains = [row['domains'] for row in trace]
    events = {(r['parameter_id'], r['requested_at_s']): r['applied_at_s'] for r in checks['original']['external_events']}
    outage, mains = (events['grid_capacity', v] for v in (2, 3.4))
    recovery = checks['original']['restoration_sample_s']
    cleaning = run['intervention_public_feedback'][0]
    for index, a in enumerate(ax):
        a.set_xlim(0, times[-1])
        a.set_facecolor(CREAM)
        a.spines[['top', 'right']].set_visible(False)
        a.spines[['bottom', 'left']].set_color(GRAY)
        a.tick_params(colors=MUTED, labelsize=9, length=0, labelbottom=index == 3)
        a.grid(axis='x', color=GRAY, lw=.65)
    demand = [d['it_service']['demand'] for d in domains]
    delivered = [d['it_service']['delivered'] for d in domains]
    ax[0].axvspan(outage, recovery, color=ORANGE, alpha=.14)
    ax[0].step(times, demand, where='post', color=BLUE, linestyle='--', lw=2, label='Offered')
    ax[0].step(times, delivered, where='post', color=TEAL, lw=2.4, label='Delivered')
    ax[0].set_ylabel('Service rate\n(normalized)', color=NAVY, labelpad=12)
    ax[0].set_ylim(-.1, 1.23)
    ax[0].set_yticks([0, .5, 1])
    ax[0].legend(loc='lower right', frameon=False, ncol=2, fontsize=9)
    ax[0].annotate('Local sample restores service', (recovery, 1), xytext=(4.55, .55),
                   color=TEAL, fontsize=9, arrowprops={'arrowstyle':'-', 'color':TEAL})
    flow = [d['facility_cooling']['lake_pump']['volume_flow_m3_s'] for d in domains]
    ax[1].step(times, flow, where='post', color=BLUE, lw=2.2)
    ax[1].set_ylabel('Intake flow\n(m³/s)', color=NAVY, labelpad=12)
    ax[1].set_yticks([0, .05, .10])
    ax[1].set_ylim(-.009, .121)
    ax[1].annotate('Filter degrades', (events['filter_resistance_multiplier', 1.5], .054),
                   xytext=(.28, .017), fontsize=9, color=MUTED, arrowprops={'arrowstyle':'-', 'color':MUTED})
    ax[1].annotate('Paid cleaning restores flow', (cleaning['observed_at_s'], .10),
                   xytext=(6.35, .034), fontsize=9, color=BLUE, arrowprops={'arrowstyle':'-', 'color':BLUE})
    ax[2].step(times, [d['power']['ups_control_from_battery_W'] for d in domains], where='post',
               color=PURPLE, lw=2, label='Internal UPS control')
    ax[2].step(times, [d['power']['ups_protected_output_W'] for d in domains], where='post',
               color=MUTED, ls='--', lw=1.8, label='UPS protected rail')
    ax[2].axvline(mains, color=MUTED, lw=.8, ls=':')
    ax[2].set_ylim(-12, 125)
    ax[2].set_yticks([0, 100])
    ax[2].set_ylabel('UPS battery\npower (W)', color=NAVY, labelpad=12)
    ax[2].legend(loc='upper right', frameon=False, ncol=2, fontsize=9)

    final = run['policy_public_decisions'][-1]['frame']['evidence']['records']
    records = {r['id']:r for r in final}
    order = records['delayed-lake-work-order']
    hand = records['actual-lake-flow-before-action']
    support = [records[key] for key in checks['original']['closure_support']]
    pairs = sorted({(r['observed_at_s'], r['arrived_at_s']) for r in support})
    last = ax[3]
    last.set_ylim(-.65, 3.65)
    last.set_yticks([3,2,1,0], ['Work order', 'Inspection', 'Cleaning', 'Recovery checks'], ha='right')
    last.set_xticks(range(11))
    last.set_xlabel('Facility time (s)', color=NAVY, labelpad=10)

    def delayed(y, sample, arrival):
        last.plot([sample, arrival], [y, y], color=MUTED, ls=':', lw=1.7, zorder=3)
        last.scatter([sample], [y], facecolor='white', edgecolor=MUTED, linewidth=1.5, s=36, zorder=4)
        last.scatter([arrival], [y], color=TEAL, s=36, zorder=4)

    delayed(3, order['observed_at_s'], order['arrived_at_s'])
    for y, work, arrival in ((2, run['work_records'][0], hand['arrived_at_s']),
                             (1, run['work_records'][1], cleaning['arrived_at_s'])):
        last.plot([work['work_started_at_s'], work['completed_at_s']], [y, y], color=BLUE,
                  lw=5, solid_capstyle='butt')
        delayed(y, work['completed_at_s'], arrival)
    for start, stop in pairs:
        delayed(0, start, stop)
    last.text(pairs[-1][1]+.17, 0, f'{pairs[-1][1]:g} s: closed', color=TEAL, fontsize=9, va='center', fontweight='bold')
    figure.legend(handles=[Line2D([0],[0], color=BLUE, lw=5, label='Actual paid work'),
                          Line2D([0],[0], marker='o', markerfacecolor='white', color=MUTED, lw=0, label='Observed or completed'),
                          Line2D([0],[0], marker='o', color=TEAL, lw=0, label='Arrived for use')],
                  loc='lower center', bbox_to_anchor=(.58,.056), ncol=3, frameon=False, fontsize=9)
    summary = run['summary']
    figure.text(.08,.033, f"Demand {summary['demand_service_unit_s']:.2f} unit·s  /  "
                f"Delivered {summary['delivered_service_unit_s']:.2f} unit·s  /  "
                f"Deficit {summary['service_deficit_time_s']:.2f} s  /  Paid work {summary['worker_work_person_s']:.2f} person·s",
                color=MUTED, fontsize=9.5)
    return figure


def architecture(scenario):
    figure = common('From facility state to verified closure',
                    'Ticket 27  /  Physical state stays private; public decisions use records after arrival', (12, 7.5))
    a = figure.add_axes([.07, .07, .86, .79])
    a.set_xlim(-1.5, 101.5)
    a.set_ylim(0, 70)
    a.axis('off')

    def box(x, y, w, h, text, color, *, fill='white', fontsize=9.5):
        a.add_patch(FancyBboxPatch((x,y), w,h, boxstyle='round,pad=.3,rounding_size=.7', lw=1.2,
                                   facecolor=fill, edgecolor=color))
        a.text(x+w/2, y+h/2, text, ha='center', va='center', color=NAVY, fontsize=fontsize, linespacing=1.4)

    def arrow(x0,y0,x1,y1,color=MUTED):
        a.add_patch(FancyArrowPatch((x0,y0),(x1,y1), arrowstyle='-|>', mutation_scale=11, lw=1.25, color=color))

    box(0, 22, 57, 43, '', '#a8bdca', fill=CREAM)
    a.text(2.3,62,'PRIVATE  /  COMPLETE V6 FACILITY', fontsize=10.5, fontweight='bold', color=NAVY)
    nodes = ['Power distribution', 'Backup energy', 'Facility cooling', 'Equipment cooling',
             'IT service', 'Local control', 'Space and access', 'People and tools']
    for index, name in enumerate(nodes):
        x, y = 2.6+26.6*(index%2), 52-8*(index//2)
        box(x,y,24.5,6,name,'#a8bdca',fontsize=9.3)
    labels = {'physical':'Physical','functional':'Functional','control_information':'Control/information','access':'Access'}
    graphs = '  /  '.join(f'{labels[key]} {len(scenario["graphs"][key])}' for key in labels)
    a.text(2.7, 24.6, graphs, color=MUTED, fontsize=8.2)
    a.text(66,62,'PUBLIC  /  EVIDENCE ONLY', fontsize=10.5,fontweight='bold',color=TEAL)
    box(65, 50, 35, 9, 'Instrument + work order\nSample, quality, provenance, arrival', TEAL, fill='#eef8f6')
    box(65, 36, 35, 9, 'Risk assessment and dispatch\nNo private state or future records', TEAL, fill='#eef8f6')
    box(65, 22, 35, 9, 'Verification by arrived evidence\nTwo signals × two observed times', TEAL, fill='#eef8f6')
    arrow(57.4,54.5,64.6,54.5,TEAL)
    arrow(82.5,49.6,82.5,45.4,TEAL)
    arrow(82.5,35.6,82.5,31.4,TEAL)
    arrow(64.6,40.5,57.4,40.5,BLUE)
    a.text(60.7,38.5,'Task',fontsize=8,color=BLUE,ha='center')
    box(0, 4, 100, 11, 'Frozen configuration + external events + policy program\nRecord original and rerun from the same inputs; compare trajectory, balances and public decisions.', BLUE, fill='#f0f4fb')
    arrow(26,15.4,26,21.6,BLUE)
    arrow(82.5,21.6,82.5,15.4,BLUE)
    a.text(24, 18.6, 'Frozen inputs', fontsize=8, color=BLUE, ha='right', va='center')
    a.text(84.2, 18.6, 'Saved outputs', fontsize=8, color=BLUE, ha='left', va='center')
    figure.text(.08, .04, 'Separate causes: local control restores service at 4 s; paid cleaning restores intake flow at 6 s.',
                color=MUTED, fontsize=9.5)
    return figure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', required=True, type=Path)
    parser.add_argument('--checks', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    runfile, tracefile, model = [args.original / name for name in ('run.json', 'private-state.jsonl', 'scenario.json')]
    run, scenario, checks = read(runfile), read(model), read(args.checks)
    assert checks['original']['status'] == checks['replay']['status'] == checks['replay_comparison']['status'] == 'PASS'
    trace = [json.loads(line) for line in tracefile.read_bytes().splitlines()]
    assert hash_file(tracefile) == run['artifacts']['private-state.jsonl']['sha256']
    assert hash_file(model) == run['artifacts']['scenario.json']['sha256']
    args.output.mkdir(exist_ok=False)
    mpl.rcParams.update({'font.family':'DejaVu Sans','svg.hashsalt':'aegisdc-ticket27'})
    for name, figure in (('27-actual-loop', chronology(trace, run, checks)), ('27-evidence-architecture', architecture(scenario))):
        figure.savefig(args.output / (name + '.png'), dpi=190, metadata={'Software':'Matplotlib ' + mpl.__version__})
        figure.savefig(args.output / (name + '.svg'), metadata={'Date': None, 'Creator':'Matplotlib ' + mpl.__version__})
        plt.close(figure)
    receipt = dict(status='RENDERED_PENDING_VISUAL_INSPECTION',
        source={name: hash_file(path) for name, path in [('original/run.json',runfile), ('original/private-state.jsonl',tracefile),
            ('original/scenario.json', model), ('replay/checks.json',args.checks)]},
        python=sys.version, executable_sha256=hash_file(Path(sys.executable)), matplotlib=mpl.__version__,
        renderer_sha256=hash_file(Path(__file__)), artifacts={p.name:hash_file(p) for p in sorted(args.output.iterdir())},
        new_project_calls=0)
    with (args.output/'render.json').open('x',encoding='utf8',newline='\n') as f:
        json.dump(receipt,f,indent=2); f.write('\n')


if __name__ == '__main__':
    main()
