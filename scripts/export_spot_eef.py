"""Export measured EEF and object motion from the published Spot recordings."""
import json
from pathlib import Path
import numpy as np
from recording_io import read_recording

ROOT = Path(__file__).resolve().parents[1]


def export():
    protocol = json.loads((ROOT/'assets/native-baseline-protocol.json').read_text())
    result = {}
    for key, scene, eef, obj in [
        ('optimized', 'mpc-spot-optimized', '/eef-overlay/current', '/body-21'),
        ('baseline', 'mpc-spot-native', '/native-overlay/current-0', '/body-25'),
    ]:
        native = next((r for r in protocol if r['scene'] == scene), None)
        if native:
            obj = '/body-' + str(native['objectBodyId'])
        record, buffers = read_recording(ROOT/f'assets/recordings/{scene}.viser')
        def positions(name):
            return {float(t): m['position'] for t, m in record['messages']
                    if m['type'] == 'SetPositionMessage' and m['name'] == name}
        hands, objects = positions(eef), positions(obj)
        assert hands and hands.keys() == objects.keys()
        if native:
            reference = [p[:2]+[.012] for p in native['objectReference']]
        else:
            ref = next(m['props']['points'] for _, m in record['messages']
                       if m.get('name') == '/object-overlay/anchors' and 'props' in m)
            reference = np.frombuffer(buffers[ref['__binary_index']], dtype=ref['dtype']).reshape(-1, 3).tolist()
        rows = [[t, *hands[t], *objects[t]] for t in sorted(hands)]
        assert np.isfinite(rows).all() and np.isfinite(reference).all()
        result[key] = dict(scene=scene, duration=record['durationSeconds'],
                           observed=rows, reference=reference,
                           eefSource=eef, objectSource=obj,
                           toppleTime=native.get('displayClip', {}).get('toppleTime') if native else None)
    return result


if __name__ == '__main__':
    data = export()
    (ROOT/'assets/spot-eef-data.js').write_text('window.CLEAR_SPOT_EEF=' + json.dumps(data, separators=(',', ':'), allow_nan=False) + ';\n')
    print('Exported measured Spot EEF samples:', {k: len(v['observed']) for k, v in data.items()})
