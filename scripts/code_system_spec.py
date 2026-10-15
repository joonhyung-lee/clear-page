"""Five source-backed modules with distinct examples."""
from html import escape

CORE = 'clear/model/clear.py'
PLANNER = 'experiments/exp3/trajectory_v3/navigation_planner.py'
EXEC = 'clear/maze/world.py'
FLOW = 'clear/model/causalflownet.py'

def node(id, title, file, symbol, stage, description, example):
    return dict(id=id,title=title,file=file,symbol=symbol,stage=stage,parent=None,
                description=description,example=example)

NODES = [
    node('representation','Representation',CORE,'SharedEncoder','grounding',
         'Robot structure is encoded together with object and scene features.', 'Planning context H'),
    node('order','Selection and order',CORE,'OrderingHead','ordering',
         'Object selection and latent interaction priorities.', 'Selected objects · order'),
    node('flow','Trajectory generation',FLOW,'RankCausalTargetFlow','generation',
         'Object trajectory generation conditioned on selection and order.', 'Object references'),
    node('verification','Feasibility checking',PLANNER,'validate_sequence','validation',
         'Sequential validation accounts for scene changes induced by preceding interactions.', 'Feasible plan'),
    node('control','Execution',EXEC,'AbstractController.interact','execution',
         'Interactions are executed in order and the observation is updated after each one.', 'Updated observation'),
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
