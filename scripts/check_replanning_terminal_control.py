"""Replay measured terminal poses through the real contact-direction code.

AST loading avoids initializing MuJoCo/Torch just to inspect the geometric
branch. --upstream intentionally fails on the captured regression.
"""
import argparse
import ast
from pathlib import Path
from types import SimpleNamespace
import time
import numpy as np

p = argparse.ArgumentParser()
p.add_argument('--project', type=Path, required=True)
p.add_argument('--upstream', action='store_true')
a = p.parse_args()
source = a.project/'experiments/exp3/trajectory_v3/native_sumo.py'
tree = ast.parse(source.read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'G1WholePathMPC')
fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'plan_object_path')
ns = dict(np=np, time=time)
exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), 'exec'), ns)
proxy_tree = ast.parse(Path(__file__).with_name('replanning_terminal_control.py').read_text())
proxy = next(n for n in proxy_tree.body if isinstance(n, ast.ClassDef) and n.name == 'ContactDirectionTracker')
exec(compile(ast.Module(body=[proxy], type_ignores=[]), 'ContactDirectionTracker', 'exec'), ns)


class Captured(Exception):
    pass


def direction(reference, actual, done, index):
    captured = []
    controller = SimpleNamespace(set_path=lambda poses: None)
    backend = SimpleNamespace(
        rt=SimpleNamespace(fixed_palm=None, contact_palm=controller),
        real=SimpleNamespace(poses=lambda oid: np.array([actual])), oid=4,
        local_tangent_guide=True,
    )
    def capture(target):
        captured.append(np.asarray(target[:2])-actual[:2])
        raise Captured()
    backend._refresh_contact = capture
    tracker = SimpleNamespace(done=done, index=index, target=reference[min(index, len(reference)-1)])
    if not a.upstream:
        tracker = ns['ContactDirectionTracker'](tracker)
    try:
        ns['plan_object_path'](backend, SimpleNamespace(poses=reference), tracker)
    except Captured:
        pass
    return captured[0]


reference = np.array([[2.36779952, 6.29063952, 0.], [2.36779952, 5.78408289, 0.]])
for name, actual in [
    ('loose waypoint complete, strict goal still pending', [2.434, 5.858, -.04]),
    ('object has passed final position', [2.41831088, 5.58227062, -.13148746]),
]:
    actual_direction = direction(reference, np.array(actual), True, 2)
    assert np.allclose(actual_direction, [0., -1.]), f'{name}: contact face changed to {actual_direction}'
    print('PASS', name, 'retains the measured push-side contact direction')
corner = np.array([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.]])
assert np.allclose(direction(corner, np.array([1., .2, 0.]), False, 2), [0., 1.])
print('PASS intermediate corner still changes direction as planned')

if not a.upstream:
    class MockBackend:
        def plan_object_path(self, path, tracker):
            return tracker
    class Overshoot(Exception):
        pass
    ns.update(G1WholePathMPC=MockBackend, ContactUnavailable=Overshoot)
    adapter = next(n for n in proxy_tree.body if isinstance(n, ast.ClassDef) and n.name == 'UprightTerminalMPC')
    exec(compile(ast.Module(body=[adapter], type_ignores=[]), 'UprightTerminalMPC', 'exec'), ns)
    backend = ns['UprightTerminalMPC']()
    backend.oid = 4
    backend.real = SimpleNamespace(poses=lambda oid: np.array([[2.368, 5.5, 0.]]))
    try:
        backend.plan_object_path(SimpleNamespace(poses=reference), SimpleNamespace(done=True))
    except Overshoot:
        print('PASS overshoot returns a failure before another forward-pushing forecast')
    else:
        raise AssertionError('Unrecoverable unilateral overshoot was not stopped')
