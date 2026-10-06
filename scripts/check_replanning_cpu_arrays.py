"""Exercise actual Warp/Torch vector conversion used by MPC state broadcast."""
import argparse
import sys
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--project', type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(a.project / 'third_party/mjlab/src'))
import torch
import warp as wp
from mjlab.sim.sim_data import TorchArray
for dtype, components in [(wp.float32, ()), (wp.vec3, (3,)), (wp.mat33, (3, 3))]:
    for shape in [(1, 0), (16, 0), (1, 2)]:
        wrapped = TorchArray(wp.zeros(shape, dtype=dtype, device='cpu'))
        assert tuple(wrapped.shape) == shape + components
        assert wrapped.dtype == torch.float32
        assert torch.count_nonzero(wrapped._tensor) == 0
    src = TorchArray(wp.zeros((1, 0), dtype=dtype, device='cpu'))
    dst = TorchArray(wp.zeros((16, 0), dtype=dtype, device='cpu'))
    dst[:] = src[0:1].expand(dst.shape[0], *src.shape[1:])
    assert dst.numel() == 0
print('PASS CPU scalar, vector and matrix shapes, empty MPC broadcast, and nonempty conversion')
