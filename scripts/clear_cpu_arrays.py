"""Scoped support for empty CPU vector arrays in the installed Warp bridge.

An empty array has no simulation state to share. NumPy supplies the vector or
matrix component dimensions that scalar-only dtype conversion omits. Nonempty
arrays continue through the installed zero-copy implementation unchanged.
"""
from contextlib import contextmanager


@contextmanager
def empty_cpu_arrays():
    import torch
    from mjlab.sim.sim_data import TorchArray
    original = TorchArray.__init__

    def initialize(self, array, nworld=None):
        if not array.device.is_cpu or array.size:
            return original(self, array, nworld=nworld)
        self._wp_array = array
        self._tensor = torch.from_numpy(array.numpy())
        if (nworld is not None and nworld > 1 and self._tensor.ndim > 0
                and self._tensor.shape[0] == 1
                and (self._tensor.stride(0) == 0 or getattr(array, '_is_batched', False))):
            self._tensor = self._tensor.expand((nworld,)+self._tensor.shape[1:])
        self._is_cuda = False
        self._torch_stream = None

    TorchArray.__init__ = initialize
    try:
        yield
    finally:
        TorchArray.__init__ = original


if __name__ == '__main__':
    import numpy as np
    import warp as wp
    from mjlab.sim.sim_data import TorchArray
    original = TorchArray.__init__
    with empty_cpu_arrays():
        for dtype, shape in [(wp.float32, (1, 0)), (wp.vec3, (1, 0, 3)),
                             (wp.quat, (1, 0, 4)), (wp.mat33, (1, 0, 3, 3))]:
            array = wp.zeros((1, 0), dtype=dtype, device='cpu')
            wrapped = TorchArray(array)
            assert tuple(wrapped.shape) == shape
            assert wrapped.numel() == 0
        array = wp.zeros((2,), dtype=wp.vec3, device='cpu')
        wrapped = TorchArray(array)
        wrapped[0, 1] = 7.
        assert array.numpy()[0, 1] == 7., 'Nonempty arrays must retain shared memory'
        wp.copy(array, wp.array(np.ones((2, 3), dtype=np.float32), dtype=wp.vec3, device='cpu'))
        assert bool((wrapped._tensor == 1.).all()), 'Warp writes must reach the tensor'
    assert TorchArray.__init__ is original
    print('PASS empty scalar/vector/matrix shapes and unchanged nonempty shared memory')
