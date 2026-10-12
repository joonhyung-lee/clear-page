"""Check published tracking measurements and their replay configuration."""
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
for body in ['g1','spot_arm']:
    evidence=json.loads((ROOT/f'assets/policy-tracking-{body}.json').read_text())
    assert evidence['protocol']['commandWorld']==[.5,0.,0.]
    assert evidence['protocol']['headingTargetRadians']==0.
    assert evidence['protocol']['headingGain']==1.
    assert len(evidence['checkpoints'])==4
    for checkpoint in evidence['checkpoints']:
        for terrain in checkpoint['terrains']:
            a=np.array(terrain['samples'])
            assert a.shape==(200,10) and np.isfinite(a).all()
            assert np.allclose(a[:,0],np.arange(200)*.04)
            assert np.allclose(a[:,1:3],[.5,0.])
            error=np.linalg.norm(a[:,3:5]-a[:,1:3],axis=1)
            assert abs(error.mean()-terrain['meanVelocityError'])<1e-5
            assert abs(np.degrees(abs(a[:,5])).mean()-terrain['meanHeadingErrorDegrees'])<1e-4
            assert np.max(np.abs(a[:,6]))<=.800001
            # Velocities and poses are physically sampled together, not cosmetic arrows.
            delta=np.gradient(a[:,7:9],.04,axis=0)
            assert np.median(np.linalg.norm(delta[1:-1]-a[1:-1,3:5],axis=1))<.2
    for terrain in evidence['checkpoints'][-1]['terrains']:
        assert terrain['forwardMotionFraction']>.95
        assert terrain['meanHeadingErrorDegrees']<3.
    name='g1-restored-data' if body=='g1' else 'spot_arm-restored-data'
    data=json.loads((ROOT/f'assets/{name}.js').read_text().rsplit(' = ',1)[1].strip().removesuffix(';'))
    assert all(stage['replay']['headingTracking'] for stage in data['checkpoints'])
    print(body,': all four checkpoint samples, recomputed errors, physical velocity/position consistency, and Step 4 forward heading PASS',flush=True)
