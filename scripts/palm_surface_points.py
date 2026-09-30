"""Map an observed surface point to the full capsule support-point position.

Normal-only support distance is enough to align a hand with an infinite plane,
but does not preserve the observed contact height or lateral coordinate on a
thin furniture rim. Keep the complete site-to-support vector in this adapter.
The source controller remains unchanged on disk.
"""
from contextlib import contextmanager
import torch
from clear.maze import palm_surface_target

_original = palm_surface_target.palm_site_targets


def palm_site_targets(controller, surface, target_rotation):
    if not hasattr(controller, '_palm_surface_geometry'):
        _original(controller, surface, target_rotation)
    centers, axes, radii, halves = controller._palm_surface_geometry
    normal = torch.cat((controller.direction, controller.direction.new_zeros(1)))
    local_normal = torch.einsum('nhij,i->nhj', target_rotation, normal)
    endpoint_sign = (local_normal * axes).sum(-1).sign()
    endpoint = centers + endpoint_sign[:, :, None] * halves[None, :, None] * axes
    world_offset = torch.einsum('nhij,nhj->nhi', target_rotation, endpoint)
    world_offset = world_offset + radii[None, :, None] * normal
    return surface - world_offset


@contextmanager
def surface_point_conversion(enabled):
    previous = palm_surface_target.palm_site_targets
    if enabled:
        palm_surface_target.palm_site_targets = palm_site_targets
    try:
        yield
    finally:
        palm_surface_target.palm_site_targets = previous
