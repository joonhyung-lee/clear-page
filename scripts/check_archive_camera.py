"""A translation-only tracking node must still move the video camera."""
from types import SimpleNamespace
import numpy as np
import render_execution_archive as module

renderer=module.ArchiveRenderer.__new__(module.ArchiveRenderer)
renderer.chase=False
renderer.body_ids={'/tracking/body-1':0}
renderer.camera_id=1
renderer.sample={('/tracking/body-1','position'):lambda t:np.array([t*3,0,.76]),('/tracking','position'):lambda t:np.array([-t*3,0,0])}
renderer.data=SimpleNamespace(mocap_pos=np.zeros((2,3)),mocap_quat=np.tile([1.,0,0,0],(2,1)))
renderer.model=object()
renderer.seek_messages=lambda t:None
renderer.draw_annotations=lambda:None
renderer.renderer=SimpleNamespace(update_scene=lambda *a,**kw:None,render=lambda:np.zeros((480,640,3),dtype=np.uint8))
module.mujoco.mj_forward=lambda *args:None
renderer.frame(2)
assert np.allclose(renderer.data.mocap_pos[1],[6,0,0]),renderer.data.mocap_pos[1]
assert np.allclose(renderer.data.mocap_quat[1],[1,0,0,0])
renderer.frame(1)
assert np.allclose(renderer.data.mocap_pos[1],[3,0,0]),'Backward seek must update the camera too'
print('PASS camera follows translation-only archives and backward seeks')
