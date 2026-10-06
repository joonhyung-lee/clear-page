"""Five source-backed modules with distinct examples."""
from html import escape

CORE = 'runtime/clear/model/clear_core.py'
PLANNER = 'runtime/experiments/exp3/trajectory_v3/navigation_planner.py'
MPC = 'runtime/experiments/exp3/trajectory_v3/native_sumo_task.py'
FLOW = 'runtime/clear/model/target_flow.py'

def node(id, title, file, symbol, stage, description, example):
    return dict(id=id,title=title,file=file,symbol=symbol,stage=stage,parent=None,
                description=description,example=example)

NODES = [
    node('representation','Representation',CORE,'SharedEncoder','grounding',
         'Robot structure is encoded together with object and scene features.', 'Planning context H'),
    node('order','Selection and order',CORE,'OrderingHead','ordering',
         'Illustrative selection and latent priority in the shared maze.', 'Selected objects · order'),
    node('flow','Trajectory generation',FLOW,'RankCausalTargetFlow','generation',
         'Illustrative rank-conditioned generation for the same selected objects and order.', 'Object references'),
    node('verification','Feasibility checking',PLANNER,'validate_sequence','validation',
         'Illustrative scene updates reveal how earlier interactions open the route for later ones.', 'Feasible plan'),
    node('control','Execution',MPC,'SumoTaskBackend','execution',
         'Recorded G1 and Spot + arm controllers track object references using updated observations.', 'Updated observation'),
]


def diagram():
    # Native buttons keep every label readable as the layout changes width.
    parts = ['<nav id="code-system" class="pipeline" aria-label="CLEAR implementation stages">',
             '<ol class="pipeline-stages">']
    for i, n in enumerate(NODES):
        parts.append(
            f'<li><button class="pipeline-node flow-node" type="button" '
            f'data-flow-node="{n["id"]}" data-flow-stage="{n["stage"]}" '
            f'role="button" tabindex="0" aria-controls="{n["stage"]}" '
            f'aria-pressed="{str(i == 0).lower()}" aria-label="{escape(n["title"])}">'
            f'<span class="pipeline-step"><span>{i+1:02d}</span></span>'
            f'<strong>{escape(n["title"])}</strong>'
            f'<span class="pipeline-output">{escape(n["example"])}</span>'
            '</button></li>'
        )
    parts.append('</ol></nav>')
    return '\n'.join(parts)
