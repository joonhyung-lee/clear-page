"""Derive the distributed source tree from the audited snapshot.

The snapshot carries the whole research tree. The distribution keeps what reproduces experiments
1-4 from the released checkpoints: the physical-execution stack (MuJoCo controllers, mjlab
runtime, sumo bridges) and modules nothing reaches are dropped, small modules are merged into
themed files, and every import is rewritten to the new names. The result is deterministic, so
the build can be repeated and diffed against the snapshot.

    python release_tools/refactor.py <snapshot/runtime> <out_dir>
"""
from __future__ import annotations

import ast
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

TOPS = ('clear', 'experiments', 'baselines', 'viz', 'scripts', 'evaluation', 'tests')

# Entry points of the distribution: the four run scripts' stages and the tests.
ENTRIES = (
    'scripts._dispatch', 'evaluation.exp1', 'experiments.exp1.cli',
    'experiments.exp2.train_comparison', 'experiments.exp2.refine_flow_comparison',
    'experiments.exp3.trajectory_v3.shared_cli',
    'experiments.exp4.sprint6h.train_adapt',
    'tests.test_candidate_orders_guard', 'tests.test_inference_recipe', 'tests.test_ordering_ablation',
    'tests.test_shared_balanced_sampling', 'tests.test_shared_morphology_v3', 'tests.model.test_flow_trace',
)

# Modules that never enter the distribution, even when something imports them lazily.
DROP_PREFIXES = ('clear.mj_util.', 'clear.low_level', 'clear.model.v4.', 'clear.data.v4.', 'clear.ego_afford',
                 'scripts.demos', 'scripts.evaluation', 'scripts.leap2026', 'scripts.training', 'scripts.train',
                 'experiments.exp5_maze_v4', 'experiments.exp3.development', 'experiments.exp3.current_cli',
                 'experiments.exp4.current_cli', 'experiments.exp4.mjlab_adapter', 'experiments.exp4.sprint6h.runner',
                 'experiments.exp3.trajectory_v3.evaluate_frozen', 'experiments.exp3.trajectory_v3.native_',
                 'experiments.exp2.evaluate_comparison', 'experiments.exp2.analyze_comparison',
                 'experiments.exp2.complete_comparison', 'viz.exp2.view_', 'tests.test_actual_target_validation')
DROP_MODULES = {
    'clear.mj_util', 'clear.model.quantizers.ema_vq', 'clear.model.quantizers.lookup_free_quantization',
    'clear.model.quantizers.residual_fsq',
    'clear.maze.mjlab_actions', 'clear.maze.mjlab_controller', 'clear.maze.mjlab_runtime', 'clear.maze.physical_controller',
    'clear.maze.sampling_mpc', 'clear.maze.contact_feedback', 'clear.maze.contact_palm', 'clear.maze.fixed_palm',
    'clear.maze.palm_clearance', 'clear.maze.palm_contact_gate', 'clear.maze.palm_force_feedback',
    'clear.maze.palm_surface_target', 'clear.maze.g1_low_contact', 'clear.maze.spot_contact', 'clear.maze.coupled_controller',
    'clear.maze.coupled_waypoints', 'clear.maze.surface_drive', 'clear.maze.transition_hold', 'clear.maze.joint_shaping',
    'clear.maze.wall_distance', 'clear.maze.execution_provenance',
}
# Kept despite the prefix rule: pure geometry the planners use.
KEEP_ANYWAY = {'clear.mj_util.push_route'}

# new module -> old modules merged into it, in dependency order (a member may import earlier members).
GROUPS = {
    'clear.model.encoders': ['clear.model.scene_encoder', 'clear.model.perception_encoder', 'clear.model.capability_encoder',
                             'clear.model.morphology_encoder', 'clear.model.structure_encoder', 'clear.model.kappa_set_encoder'],
    'clear.model.affordancenet': ['clear.model.affordance_transformer', 'clear.model.stageb_aux_heads'],
    'clear.model.ordernet': ['clear.model.ordering_ablation_heads', 'clear.model.priority_head', 'clear.model.ordering_loss',
                             'clear.model.plan_scorer'],
    'clear.model.causalflownet': ['clear.model.causal_velocity_field', 'clear.model.target_flow',
                                  'clear.model.dynamics_prediction_flow', 'clear.model.flow_rate_baseline'],
    'clear.model.quantizers': ['clear.model.quantizers.finite_scalar_quantization'],
    'clear.model.clear': ['clear.model.clear_core', 'clear.model.affordance_conditioned_core', 'clear.model.v4.plan_code',
                          'clear.model.pamo'],
    'clear.data.terrain': ['clear.data.terrain', 'clear.data.terrain_primitives', 'clear.data.capability_terrain'],
    'clear.data.ego': ['clear.data.ego_scene', 'clear.data.ego_project', 'clear.data.ego_render'],
    'clear.data.modes': ['clear.data.v4.modes'],
    'clear.util': ['clear.util.project', 'clear.util.placement', 'clear.util.ranking', 'clear.util.schedule', 'clear.util.shift',
                   'clear.util.validity', 'clear.maze.qd_cem'],
    'clear.maze.world': ['clear.mj_util.push_route', 'clear.maze.tile_surface', 'clear.maze.controller_interface'],
    'clear.maze.robots': ['clear.maze.robot_registry', 'clear.maze.structure_parser', 'clear.maze.physical_registry'],
}
RENAMES = {'scripts._dispatch': 'experiments.common.dispatch', 'evaluation.exp1': 'experiments.exp1.evaluate',
           'clear.model.quantizers': 'clear.model.quantizers'}

# Exact-text edits that remove code paths of the dropped stack (applied before merging).
PATCHES: dict[str, list[tuple[str, str]]] = {
    # grid oracle: the push-feasibility branches (PAMO_PUSHABLE_* flags) route through the dropped executor code
    'clear.data.oracle': [
        ("""            if PUSHABLE_PLAN:
                # a PUSHING robot entering the object's cell from `cell` shoves the object one cell further
                # in the same direction: that cell must exist, not be WALL and not hold an unmoved object
                # (PLAN 132). Without this the search happily "moves" a doorway blocker into the wall behind it.
                ahead = (nxt[0] + dr, nxt[1] + dc)
                push_ok = scene.in_bounds(ahead) and int(scene.terrain[ahead]) != WALL and \\
                    (occ.get(ahead) is None or occ.get(ahead) in moved)
                # a dragging body (PLAN 134) may instead pull the object onto its own cell and retreat one cell
                back = (cell[0] - dr, cell[1] - dc)
                pull_ok = getattr(emb, "can_drag", False) and scene.in_bounds(back) and \\
                    int(scene.terrain[back]) != WALL and (occ.get(back) is None or occ.get(back) in moved)
                if not (push_ok or pull_ok):
                    continue
""", ""),
        ("""from contextvars import ContextVar

PUSHABLE_PARKS_OVERRIDE = ContextVar("pushable_parks", default=None)


def _pushable_parks():
    override = PUSHABLE_PARKS_OVERRIDE.get()
    return PUSHABLE_PARKS if override is None else override


PUSHABLE_PARKS = os.environ.get("PAMO_PUSHABLE_PARKS", "0") == "1"  # see find_parking.valid (PLAN 129)
PUSHABLE_PLAN = os.environ.get("PAMO_PUSHABLE_PLAN", "0") == "1"    # solve() push-feasible moves + prune_unpushable (PLAN 132)
if PUSHABLE_PLAN:
    PUSHABLE_PARKS = True


""", ""),
        ("""        if _pushable_parks():
            # 2026-08-28 (PLAN 129): the carry BFS accepts parks a PUSHING robot cannot reach -- the robot must
            # stand behind the object every step and walk around it at every turn (Sokoban). rooms 1009: the
            # doorway blocker's park along the corridor is carry-reachable but unpushable (its west side is a
            # wall); both executors spent their budget on it. Opt-in (env PAMO_PUSHABLE_PARKS=1) because it
            # changes training labels.
            from clear.mj_util.push_route import pushable_path
            blocked = {c for j, c in enumerate(positions) if c is not None and j != i}
            if pushable_path(scene, positions[i], cand, blocked, robot_cell=robot_cell,
                             can_drag=getattr(emb, "can_drag", False)) is None:
                return False
""", ""),
        ("""    if _pushable_parks():
        # second tier (2026-08-28): no candidate is both pushable and plan-valid (rooms doorway blockers: the only
        # pushable move is one cell into the corridor, which the cell-level plan check calls a block). Prefer a
        # pushable park that fails the abstract plan check over the unpushable nearest-free fallback -- the
        # physical executors squeeze past a box in a 1.475 m corridor more often than the cell check admits.
        from clear.mj_util.push_route import pushable_path
        blocked = {c for j, c in enumerate(positions) if c is not None and j != i}
        for cand in candidates:
            if pushable_path(scene, positions[i], cand, blocked, robot_cell=robot_cell,
                             can_drag=getattr(emb, "can_drag", False)) is not None:
                return cand
""", ""),
        ("""    robot_cell = tuple(scene.start) if _pushable_parks() else None
""", """    robot_cell = None
"""),
        ("""        if robot_cell is not None:
            # where the pusher ends: the cell the object left last (behind it on the final segment)
            from clear.mj_util.push_route import pushable_path
            blocked = {c for j, c in enumerate(positions) if c is not None and j != i}
            path = pushable_path(scene, positions[i], cand, blocked, robot_cell=robot_cell)
            if path is not None and len(path) > 1:
                robot_cell = tuple(path[-2])
""", ""),
    ],
    # grid data: the metric-parking label variant refines poses with the dropped executor geometry
    'clear.data.data': [
        ('@remove', '_metric_label_pose'),
        ("""            if metric_labels:
                # continuous, wall-clearance-maximizing park pose within the oracle's
                # cell decision (metric-parking layer 1, label side) -- replaces the
                # uninformative uniform jitter; the jitter draw is still consumed so
                # the scene/x0 stream stays paired with the non-metric run
                _ = jitter_rng.uniform(-JITTER, JITTER, size=2)
                # sequential-parking context mirroring assign_goal_cells(work, union):
                # union members BEFORE i already sit at their goal cells, the rest at
                # their start cells; pending = union members after i
                k_i = union.index(i)
                positions = [work.objects[j].goal_cell if (j in union and union.index(j) < k_i)
                             else work.objects[j].cell for j in range(len(work.objects))]
                x1[i, :2] = _metric_label_pose(work, i, x0[i, :2], emb=emb,
                                               pending=union[k_i + 1:], positions=positions)
            else:
                x1[i, :2] = (c + jitter_rng.uniform(-JITTER, JITTER), r + jitter_rng.uniform(-JITTER, JITTER))
""", """            x1[i, :2] = (c + jitter_rng.uniform(-JITTER, JITTER), r + jitter_rng.uniform(-JITTER, JITTER))
"""),
    ],
    'clear.mj_util.push_route': [('@remove', '_diag')],
    # maze world: only the abstract controller ships
    'clear.maze.controller_interface': [
        ("""    if name == 'mjlab_surface':
        from clear.maze.coupled_controller import SurfaceController
        return SurfaceController(scene,body,**kw)
    if name == 'mjlab_native':
        from clear.maze.mjlab_controller import MjlabController
        return MjlabController(scene,body,**kw)
    if name == "mujoco_policy":
        from clear.maze.physical_controller import PhysicalController
        return PhysicalController(scene, body, **kw)
""", ""),
        ("""    "mocap": _unavailable("mocap", "this controller was never implemented; use abstract, mujoco_policy, or mjlab_native"),
    "sumo_spot": _unavailable("sumo_spot", "needs third-party/sumo's pixi env (judo CEM whole-body controller); "
                              "adapter: clear.mj_util.spot_push_bridge.execute_plan_physically"),
    "mjlab": _unavailable("mjlab", "needs a GPU (mjlab RL walkers, clear/low_level/); "
                          "adapter: clear-locomotion task_maze/board_push.py"),
""", """    "mujoco_policy": _unavailable("mujoco_policy", "physical execution is not part of this distribution"),
    "mjlab_native": _unavailable("mjlab_native", "physical execution is not part of this distribution"),
"""),
    ],
    # ego affordance: analytic contact scoring only (the learned sampler lived in the dropped mj_util)
    'clear.maze.ego_affordance': [
        ("""        self._net = None
        if contact_ckpt is not None:
            try:
                from clear.mj_util.contact_net import load_sampler
                self._net = load_sampler(contact_ckpt, device=device).net
            except Exception:   # ponytail: missing ckpt / torch -> analytic only
                self._net = None
""", """        self._net = None   # the learned contact sampler is not part of this distribution: analytic scoring only
"""),
        ("""        elif self._net is not None:
            try:
                from clear.mj_util.contact_net import sample_contact_learned
                local_pts = pts.copy(); local_pts[:, 2] -= support_z
                learned_height = (0.5 * (z_lo + z_hi) if self.contact_prior_height_m is None else z_preferred) - support_z
                cs = sample_contact_learned(local_pts, rgb, d, push_height_m=learned_height,
                                            net=self._net, device=self.device, mode='argmax', rng=self.rng)
                if cs.ok:
                    world_point = np.asarray(cs.point_world) + np.array([0., 0., support_z])
                    q = q * np.exp(-((cand - world_point) ** 2).sum(1) / 0.05 ** 2)
                    scorer = 'contact_net'
            except Exception:
                pass
""", ""),
    ],
    'clear.maze.physical_registry': [
        ("from dataclasses import replace\nfrom clear.maze import robot_registry as R\n", "from dataclasses import replace\n"),
        ("    from clear.maze import structure_parser\n", ""),
        ("R.REGISTRY", "REGISTRY"), ("R.VARIANT_SEP", "VARIANT_SEP"), ("structure_parser._CACHE", "_CACHE"),
    ],
    # mjlab-compiled quadruped bodies are not part of this distribution
    'experiments.exp3.trajectory_v3.unseen_bodies': [
        ("""def _mjlab_structure(body, entry):
    \"\"\"StructureDescription of the entity mjlab compiles for the walker (asset + position actuators).\"\"\"
    import numpy as np
    from mjlab.entity.entity import Entity
    from clear.data.morphology import link_rows_v3_from_model
    from clear.maze import structure_parser as sp
    if body == "go1":
        from mjlab.asset_zoo.robots.unitree_go1.go1_constants import get_go1_robot_cfg as cfg
        model = Entity(cfg()).spec.compile()
    elif body == "go2":
        from clear.low_level.task_go2.go2_constants import get_go2_robot_cfg as cfg
        model = Entity(cfg()).spec.compile()
    else:
        from clear.low_level.task_quadrupeds import entity_cfg
        base, _, m = body.partition("_m")
        model = Entity(entity_cfg(base, float(m.replace("p", ".")) if m else 1.0)).spec.compile()
    rows = link_rows_v3_from_model(model).astype(np.float32)
    links = sp._links_schema(model)
    assert rows.shape[1] == sp.STRUCTURE_DIM and len(links) == rows.shape[0] and np.isfinite(rows).all()
    desc = sp.StructureDescription(body, entry.asset, [], links, rows)
    desc.structure_hash = sp.structure_hash(links)
    return desc


""", ""),
        ("""    from clear.maze import structure_parser as sp
    for key, entry in {**entries(), **variant_entries()}.items():
        if key in R.REGISTRY and R.REGISTRY[key].asset != entry.asset:
            raise KeyError(f"{key} already registered with a different asset")
        R.REGISTRY.setdefault(key, entry)
        if (key in ("go1", "go2") or key in variant_entries()) and key not in sp._CACHE:
            sp._CACHE[key] = _mjlab_structure(key, entry)
""", """    for key, entry in {**entries(), **variant_entries()}.items():
        if key in R.REGISTRY and R.REGISTRY[key].asset != entry.asset:
            raise KeyError(f"{key} already registered with a different asset")
        R.REGISTRY.setdefault(key, entry)
"""),
    ],
    'clear.maze': [('@file', '"""Maze world model: `world` (scenes, observations, routes, the abstract controller) and\n'
                             '`robots` (body registry and link-level structure descriptions)."""\n')],
    'tests.test_inference_recipe': [
        ("    from scripts.evaluation.eval_ood import scene_fn_for\n",
         "    from clear.data.grid import gp_scene, random_scene\n    from clear.data.probes import rooms_fork_scene\n\n"
         "    def scene_fn_for(name, g, n_obj):\n"
         "        if name == 'rooms_fork':\n            return lambda r: rooms_fork_scene(r, g, g, n_obj)\n"
         "        return lambda r: gp_scene(r, g, g, n_obj) if r.random() < 0.7 else random_scene(r, g, g, n_obj)\n"),
    ],
    'scripts._dispatch': [
        ("""    return int(fn(rest) or 0)
""", """    return int(fn(rest) or 0)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2:]))
"""),
        ('prog=f"python -m scripts.{command}"', 'prog=f"run_01_grid.py {command}"'),
    ],
    'experiments.exp1.cli': [('methods = list(ecfg.get("methods", METHODS))', 'methods = list(ecfg.get("methods", ALL_METHODS))')],
    'experiments.common.registry': [
        ('    "exp1": "experiments.exp1.cli",\n    "exp2": "experiments.exp2.cli",\n    "exp3": "experiments.exp3.current_cli",\n'
         '    "exp4": "experiments.exp4.current_cli",\n    "sequential-manipulation": "experiments.exp2.cli",\n'
         '    "grid2d": "experiments.exp1.cli",\n    "maze_embodiment": "experiments.exp3.cli",\n'
         '    "maze_long_horizon": "experiments.exp4.cli",\n',
         '    "grid2d": "experiments.exp1.cli",\n'),
        ('    if legacy and experiment in ("exp3", "exp4"):\n        module = f"experiments.{experiment}.cli"\n', ''),
    ],
}


def module_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix('')
    parts = rel.parts[:-1] if rel.name == '__init__' else rel.parts
    return '.'.join(parts)


def discover(root: Path) -> dict[str, Path]:
    mods = {}
    for top in TOPS:
        for p in sorted((root / top).rglob('*.py')):
            if '__pycache__' not in p.parts:
                mods[module_name(root, p)] = p
    return mods


GROUP_MEMBERS = {m for ms in GROUPS.values() for m in ms}


def dropped(name: str) -> bool:
    if name in KEEP_ANYWAY or name in GROUP_MEMBERS:
        return False
    return name in DROP_MODULES or name.startswith(DROP_PREFIXES)


def resolve(name: str, mods) -> str | None:
    while name:
        if name in mods:
            return name
        name = name.rpartition('.')[0]
    return None


def absolute(node: ast.ImportFrom, module: str, is_init: bool) -> str:
    if not node.level:
        return node.module or ''
    pkg = module if is_init else module.rpartition('.')[0]
    parts = pkg.split('.')
    base = parts[:len(parts) - node.level + 1]
    return '.'.join(base + ([node.module] if node.module else []))


def exports(pkg: str, mods, sources) -> dict[str, str]:
    """name -> defining module for names a package __init__ re-exports."""
    table = {}
    if pkg not in mods or mods[pkg].name != '__init__.py':
        return table
    for node in ast.parse(sources[pkg]).body:
        if isinstance(node, ast.ImportFrom):
            base = absolute(node, pkg, True)
            for a in node.names:
                table[a.asname or a.name] = resolve(base + '.' + a.name, mods) or resolve(base, mods)
    return table


def references(src: str, module: str, is_init: bool, mods, sources) -> set[str]:
    """Modules a source file refers to in import statements (lazy imports included); a name imported
    from a package resolves to the module that package re-exports it from."""
    out = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = absolute(node, module, is_init)
            names = [base] + [base + '.' + a.name for a in node.names]
            table = exports(resolve(base, mods), mods, sources) if resolve(base, mods) == base else {}
            out.update(t for t in (table.get(a.name) for a in node.names) if t)
        else:
            continue
        out.update(r for r in (resolve(n, mods) for n in names) if r)
    return out


def closure(mods, sources) -> set[str]:
    """Static reachability from ENTRIES; package __init__ re-exports do not count as edges."""
    seen, stack = set(), list(ENTRIES)
    while stack:
        m = stack.pop()
        if m in seen or dropped(m) or m not in mods:
            continue
        seen.add(m)
        if mods[m].name != '__init__.py':
            stack.extend(references(sources[m], m, False, mods, sources) - seen)
    for m in list(seen):   # a reachable module needs its parent packages
        parts = m.split('.')
        for i in range(1, len(parts)):
            pk = '.'.join(parts[:i])
            if pk in mods and not dropped(pk):
                seen.add(pk)
    return seen


class Edit:
    def __init__(self, src: str):
        self.lines = src.splitlines(keepends=True)
        self.edits: list[tuple[int, int, str]] = []

    def replace(self, node: ast.AST, text: str):
        indent = re.match(r'\s*', self.lines[node.lineno - 1]).group(0)
        body = '\n'.join(indent + t for t in text.split('\n')) + '\n' if text else ''
        self.edits.append((node.lineno - 1, node.end_lineno, body))

    def result(self) -> str:
        for start, end, body in sorted(self.edits, reverse=True):
            self.lines[start:end] = [body] if body else []
        return ''.join(self.lines)


def remove_toplevel(src: str, target: str) -> str:
    """Delete the top-level def/class/assignment that binds `target`."""
    tree = ast.parse(src)
    edit, hit = Edit(src), False
    for node in tree.body:
        bound = [node.name] if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else \
            [t.id for t in getattr(node, 'targets', []) if isinstance(t, ast.Name)]
        if target in bound:
            edit.replace(node, ''); hit = True
    if not hit:
        raise ValueError(f'nothing named {target} to remove')
    return edit.result()


def apply_patches(name: str, src: str) -> str:
    for old, new in PATCHES.get(name, []):
        if old == '@remove':
            src = remove_toplevel(src, new)
            continue
        if old == '@file':
            src = new
            continue
        if old not in src:
            raise ValueError(f'patch for {name} does not match: {old[:60]!r}')
        src = src.replace(old, new)
    return src


def fmt_names(names) -> str:
    return ', '.join(n + (f' as {a}' if a and a != n else '') for n, a in names)


def rewrite_imports(src: str, module: str, is_init: bool, mods, old2new, kept, sources) -> tuple[str, list[str]]:
    """Rewrite import statements to the new module names; report imports of dropped modules."""
    tree = ast.parse(src)
    edit, problems = Edit(src), []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                r = resolve(a.name, mods)
                if r and r not in kept:
                    problems.append(f'import {a.name}')
                elif r and old2new.get(r, r) != r:
                    problems.append(f'plain import of renamed module {a.name}')
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        base = absolute(node, module, is_init)
        rbase = resolve(base, mods)
        if rbase is None:
            continue
        groups: dict[str, list] = defaultdict(list)
        for a in node.names:
            full = resolve(base + '.' + a.name, mods)
            if full == base + '.' + a.name and full in mods:      # importing a submodule by name
                if full not in kept:
                    if not is_init:
                        problems.append(f'from {base} import {a.name}')
                    continue
                new = old2new.get(full, full)
                if new == old2new.get(rbase, rbase):               # package collapsed into one module: name is now an attribute
                    groups[new].append((a.name, a.asname))
                else:
                    pkg, _, leaf = new.rpartition('.')
                    groups[pkg].append((leaf, a.asname or a.name))
            else:
                origin = exports(rbase, mods, sources).get(a.name) if rbase == base else None
                if rbase not in kept or (origin and origin not in kept):
                    if not is_init:
                        problems.append(f'from {base} import {a.name}')
                    continue
                groups[old2new.get(rbase, rbase)].append((a.name, a.asname))
        new_text = '\n'.join(f'from {m} import {fmt_names(ns)}' for m, ns in groups.items())
        old_text = ast.get_source_segment(src, node)
        if new_text and new_text != old_text and not (node.level and all(m == rbase for m in groups)):
            edit.replace(node, new_text)
        elif not new_text:
            edit.replace(node, '')
    text = edit.result()
    if is_init:
        text = prune_all(text)
    return text, problems


def prune_all(src: str) -> str:
    """Keep only names that the module still binds in its __all__ list."""
    tree = ast.parse(src)
    bound = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            bound.update((a.asname or a.name).split('.')[0] for a in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            bound.update(t.id for t in node.targets if isinstance(t, ast.Name))
    edit = Edit(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__all__' for t in node.targets) \
                and isinstance(node.value, (ast.List, ast.Tuple)):
            names = [e.value for e in node.value.elts if isinstance(e, ast.Constant) and e.value in bound]
            edit.replace(node, '__all__ = [\n' + ''.join(f'    {n!r},\n' for n in names) + ']')
    return edit.result()


def strip_for_merge(src: str, member: str, group: list[str], mods, collisions: dict[str, str]) -> tuple[str, str | None, set[str], list[str]]:
    """Prepare one member for concatenation: drop its docstring, __future__ imports, imports of other
    members, __all__, and `if __name__ == '__main__'` blocks; rename colliding private names."""
    tree = ast.parse(src)
    edit, futures, doc = Edit(src), set(), ast.get_docstring(tree, clean=False)
    imports = []
    body = tree.body
    if doc is not None:
        edit.replace(body[0], '')
    for node in body:
        if isinstance(node, ast.ImportFrom) and node.module == '__future__':
            futures.update(a.name for a in node.names)
            edit.replace(node, '')
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(ast.get_source_segment(src, node))
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__all__' for t in node.targets):
            edit.replace(node, '')
        elif isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and ast.unparse(node.test).startswith('__name__ =='):
            edit.replace(node, '')
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = absolute(node, member, False)
            target = resolve(base, mods)
            if target in group and target != member:
                edit.replace(node, '')
            elif base == member.rpartition('.')[0] and any(resolve(base + '.' + a.name, mods) in group for a in node.names):
                edit.replace(node, '')   # `from pkg import sibling_module` inside the group
    out = edit.result()
    for name, suffix in collisions.items():
        out = re.sub(rf'\b{re.escape(name)}\b', f'{name}_{suffix}', out)
    return out, doc, futures, imports


def dedupe_imports(src: str, seen: set) -> str:
    """Drop top-level imports of names an earlier member of the merged module already imported."""
    tree = ast.parse(src)
    edit = Edit(src)
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            keep = [(a.name, a.asname) for a in node.names if (node.module, a.name, a.asname) not in seen]
            seen.update((node.module, a.name, a.asname) for a in node.names)
            if len(keep) != len(node.names):
                edit.replace(node, f'from {node.module} import {fmt_names(keep)}' if keep else '')
        elif isinstance(node, ast.Import):
            keep = [(a.name, a.asname) for a in node.names if ('import', a.name, a.asname) not in seen]
            seen.update(('import', a.name, a.asname) for a in node.names)
            if len(keep) != len(node.names):
                edit.replace(node, 'import ' + fmt_names(keep) if keep else '')
    return edit.result()


def toplevel_defs(src: str) -> dict[str, str]:
    names = {}
    for node in ast.parse(src).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names[node.name] = ast.get_source_segment(src, node)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                for x in ast.walk(t):
                    if isinstance(x, ast.Name):
                        names[x.id] = ast.get_source_segment(src, node)
    return names


def merge(new: str, members: list[str], sources: dict[str, str], mods) -> str:
    seen_defs: dict[str, tuple[str, str]] = {}
    collisions: dict[str, dict[str, str]] = defaultdict(dict)
    for m in members:
        for name, text in toplevel_defs(sources[m]).items():
            if name in seen_defs and seen_defs[name][1] != text:
                if not name.startswith('_'):
                    raise ValueError(f'{new}: {name} is defined differently in {seen_defs[name][0]} and {m}')
                collisions[m][name] = m.rsplit('.', 1)[-1]
            seen_defs.setdefault(name, (m, text))
    parts, docs, futures, seen_imports = [], [], set(), set()
    for m in members:
        text, doc, fut, imports = strip_for_merge(sources[m], m, members, mods, collisions[m])
        futures |= fut
        if doc:
            docs.append((m, doc.strip()))
        text = dedupe_imports(text, seen_imports)
        parts.append(f'# ---- {m.rsplit(".", 1)[-1]} ----\n' + text.strip('\n') + '\n')
    head = f'"""{new.rsplit(".", 1)[-1]}: ' + ', '.join(m.rsplit('.', 1)[-1] for m in members) + '.\n\n'
    head += '\n\n'.join(f'{m.rsplit(".", 1)[-1]}: ' + d for m, d in docs) + '\n"""\n'
    if futures:
        head += 'from __future__ import ' + ', '.join(sorted(futures)) + '\n'
    return head + '\n' + '\n\n'.join(parts)


def build(runtime: Path) -> dict[str, str]:
    """Return {relative path: source} for the distributed Python files."""
    mods = discover(runtime)
    sources = {m: p.read_text() for m, p in mods.items()}
    for m in list(sources):
        sources[m] = apply_patches(m, sources[m])
    kept = closure(mods, sources)
    old2new = dict(RENAMES)
    for new, members in GROUPS.items():
        for m in members:
            old2new[m] = new
    # the merged modules exist only if a member is reachable
    kept_groups = {new: [m for m in members if m in kept] for new, members in GROUPS.items()}
    kept_groups = {new: ms for new, ms in kept_groups.items() if ms}
    kept_all = set(kept) | set(kept_groups)
    out: dict[str, str] = {}
    for new, members in kept_groups.items():
        out[new] = merge(new, members, sources, mods)
    for m in kept:
        if (m in old2new and m not in RENAMES) or m in GROUPS:
            continue   # merged above (a package collapsed into one module loses its __init__)
        out[old2new.get(m, m)] = sources[m]
    problems = []
    final: dict[str, str] = {}
    for name, src in out.items():
        is_init = name in mods and mods[name].name == '__init__.py' and name not in GROUPS
        text, bad = rewrite_imports(src, name, is_init, mods, old2new, kept_all, sources)
        problems += [f'{name}: {b}' for b in bad]
        rel = Path(*name.split('.'))
        rel = rel / '__init__.py' if is_init else rel.with_suffix('.py')
        final[str(rel)] = text
    if problems:
        raise ValueError('imports of dropped modules remain:\n  ' + '\n  '.join(problems))
    for rel in [r for r in final if r.endswith('__init__.py')]:
        pkg = rel[:-len('__init__.py')]
        if not any(r != rel and r.startswith(pkg) for r in final):
            del final[rel]
    return final


def main():
    runtime, out = Path(sys.argv[1]), Path(sys.argv[2])
    files = build(runtime)
    for rel, text in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    digest = hashlib.sha256(''.join(f'{k}\0{v}' for k, v in sorted(files.items())).encode()).hexdigest()
    print(f'{len(files)} files -> {out}  tree sha256 {digest[:12]}')


if __name__ == '__main__':
    main()
