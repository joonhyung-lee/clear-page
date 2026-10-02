"""Verify the actual video renderer follows G1 in both published scene formats."""
import numpy as np
from render_execution_archive import ArchiveRenderer

for scene,chase in [('mpc-g1-native',True),('mpc-baseline',False)]:
    renderer=ArchiveRenderer(scene,chase=chase)
    states=[]
    try:
        camera=renderer.model.camera('main').id
        body=renderer.model.body(renderer.prefix+'/body-1').id
        for time in [2.,10.,30.]:
            frame=renderer.frame(time)
            base=renderer.data.xpos[body].copy()
            eye=renderer.data.cam_xpos[camera].copy()
            basis=renderer.data.cam_xmat[camera].reshape(3,3).copy()
            assert frame.std()>10 and np.isfinite(frame).all()
            states.append((base,eye,basis))
        first=states[0]
        for base,eye,basis in states[1:]:
            assert np.linalg.norm(base[:2]-first[0][:2])>.1
            assert np.allclose(eye[:2]-base[:2],first[1][:2]-first[0][:2],atol=1e-7)
            assert np.allclose(eye[2],first[1][2],atol=1e-7)
            assert np.allclose(basis,first[2],atol=1e-7)
        print('PASS',scene,'rendered camera follows horizontal body motion at 2, 10, 30 s',flush=True)
    finally:
        renderer.renderer.close()
