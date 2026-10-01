"""Verify native robot dynamics and bake exact saved poses for publication."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import mujoco
import numpy as np
import sumo.tasks
import sumo.controller
from sumo.run_mpc.run_mpc import _create_sim
from judo.optimizers import get_registered_optimizers
from sumo.controller import ControllerConfig

from record_native_baseline import prepare_spot_assets, dump


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--spot-assets', type=Path)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    result = json.loads((a.source/'result.json').read_text())
    protocol = json.loads((a.source/'protocol.json').read_text())
    assert protocol['nativeController'] and protocol['nativeArmReset']
    for flag in ['cartesianTracking', 'addedJointSmoothing', 'addedJitter', 'gainOverride', 'commandHoldOverride']:
        assert protocol[flag] is False, flag
    for source, digest in protocol['sourceSHA256'].items():
        assert hashlib.sha256(Path(source).read_bytes()).hexdigest() == digest
    if a.spot_assets:
        prepare_spot_assets(a.spot_assets, a.output)
    original = _create_sim(result['task']).task
    native = original.model
    model = mujoco.MjModel.from_binary_path(str(a.source/'task.mjb'))
    # Every named robot body, joint, and actuator must retain native dynamics.
    nbody = 0
    for i in range(1, native.nbody):
        name = native.body(i).name
        if name in ['box_body', 'box', 'table', 'large_box']:
            continue
        j = model.body(name).id
        for field in ['mass', 'inertia', 'ipos', 'iquat', 'pos', 'quat']:
            assert np.allclose(getattr(native, 'body_'+field)[i], getattr(model, 'body_'+field)[j]), (name, field)
        nbody += 1
    for i in range(native.njnt):
        name = native.joint(i).name
        if name == 'box_joint':
            continue
        j = model.joint(name).id
        for field in ['type', 'axis', 'pos', 'limited', 'range', 'stiffness']:
            assert np.allclose(getattr(native, 'jnt_'+field)[i], getattr(model, 'jnt_'+field)[j]), (name, field)
    assert model.nu == native.nu
    for i in range(native.nu):
        j = model.actuator(native.actuator(i).name).id
        for field in ['gainprm', 'biasprm', 'dynprm', 'gear', 'ctrlrange', 'forcerange', 'ctrllimited', 'forcelimited']:
            assert np.allclose(getattr(native, 'actuator_'+field)[i], getattr(model, 'actuator_'+field)[j]), (i, field)
    cc = ControllerConfig(); cc.set_override(result['task'])
    _, cls = get_registered_optimizers()['cem']; oc = cls(); oc.set_override(result['task'])
    assert asdict(cc) == protocol['controllerConfig'] and asdict(oc) == protocol['optimizerConfig']
    for key, value in asdict(original.config).items():
        if key != 'goal_position':
            assert np.allclose(value, protocol['taskConfig'][key]), key
    assert np.allclose(protocol['initialQpos'][7:26 if result['robot']=='spot_arm' else 36],
                       original.reset_pose[7:26 if result['robot']=='spot_arm' else 36])
    source = np.load(a.source/'states.npz')
    times = source['time']
    assert np.all(np.diff(times)>0) and np.all(np.isfinite(source['qpos']))
    data = mujoco.MjData(model)
    positions, quaternions, eef = [], [], []
    for qpos in source['qpos']:
        data.qpos[:] = qpos
        mujoco.mj_forward(model, data)
        positions.append(data.xpos.copy()); quaternions.append(data.xquat.copy())
        eef.append(data.site_xpos[[model.site(n).id for n in result['eefSites']]].copy())
    positions = np.asarray(positions)
    np.savez_compressed(a.output/'states.npz', time=times, qpos=source['qpos'],
        positions=positions, quaternions=quaternions, eef=eef)
    geometry = dict(np.load(a.source/'geometry.npz'))
    # Neutral presentation of the physical floor and boundary walls only.
    geometry['geom_rgba'] = geometry['geom_rgba'].copy()
    geometry['geom_matid'] = geometry['geom_matid'].copy()
    for i in range(model.ngeom):
        if model.geom_bodyid[i] == 0:
            geometry['geom_matid'][i] = -1
            geometry['geom_rgba'][i] = [.86,.89,.86,1.]
    np.savez_compressed(a.output/'geometry.npz', **geometry)
    threshold = getattr(original.config, 'fall_threshold', .35)
    falls = np.flatnonzero(source['qpos'][:,2] <= threshold)
    result['fell'] = bool(len(falls))
    result['firstFallTime'] = float(times[falls[0]]) if len(falls) else None
    target = result['objectBodyId']
    goal = np.asarray(result['taskConfig']['goal_position'])
    points = np.r_[source['qpos'][:,:3], positions[:,target], goal[None,:]]
    low, high = points.min(0), points.max(0)
    center = (low+high)/2; center[2] = .65
    extent = max(high[:2]-low[:2])
    eye = center + np.array([-1.05,-1.3,.95])*max(2.7,extent*.78)
    result['camera'] = dict(target=center.tolist(),position=eye.tolist(),fov=.75)
    result['verification'] = dict(nativeBodies=nbody, nativeActuators=int(native.nu),
        sourceMethodsMatched=True, originalCosts=True, originalCEM=True, exactRecordedFK=True,
        frames=len(times), fullAttempt=True)
    result['eefLocalPositions'] = [model.site(n).pos.tolist() for n in result['eefSites']]
    result['initialArmPositions'] = source['qpos'][0,protocol['armJointAddresses']].tolist()
    result['scope'] += ' Full attempt from reset. EEF markers show measured sites, not commanded Cartesian targets.'
    dump(a.output/'result.json', result)
    print('PASS native dynamics, costs, CEM, reset and recorded FK',result['robot'],len(times),flush=True)


if __name__ == '__main__':
    main()
