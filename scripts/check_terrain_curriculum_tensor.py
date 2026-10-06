"""Exercise native terrain promotion using real CPU tensors and sparse env IDs."""
from types import SimpleNamespace
import torch
from mjlab.terrains.terrain_entity import TerrainEntity
from mjlab.tasks.velocity.mdp.curriculums import terrain_levels_vel


class Scene(dict):
    pass


terrain = TerrainEntity.__new__(TerrainEntity)
terrain.cfg = SimpleNamespace(terrain_generator=SimpleNamespace(size=(8., 8.), sub_terrains={'flat': None}))
terrain.terrain_levels = torch.zeros(4, dtype=torch.long)
terrain.terrain_types = torch.zeros(4, dtype=torch.long)
terrain.max_terrain_level = 3
terrain.terrain_origins = torch.tensor([[[0., 0., 0.]], [[8., 0., 0.]], [[16., 0., 0.]]])
terrain.env_origins = torch.zeros(4, 3)
robot = SimpleNamespace(data=SimpleNamespace(root_link_pos_w=torch.tensor([[0., 0., 0.], [5., 0., 0.], [0., 0., 0.], [.1, 0., 0.]])))
scene = Scene(robot=robot)
scene.terrain = terrain
scene.env_origins = terrain.env_origins
env = SimpleNamespace(scene=scene, common_step_counter=1, max_episode_length_s=20,
    command_manager=SimpleNamespace(get_command=lambda _: torch.tensor([[.5, 0., 0.]]*4)))
ids = torch.tensor([1, 3])
metric = terrain_levels_vel(env, ids, 'twist')
assert terrain.terrain_levels.tolist() == [0, 1, 0, 0], 'Sparse indexing must update the real levels'
assert metric['mean'].item() == .25 and metric['max'].item() == 1
assert terrain.env_origins[1, 0] == 8
robot.data.root_link_pos_w[1, 0] = 8.1
terrain_levels_vel(env, ids, 'twist')
assert terrain.terrain_levels.tolist() == [0, 0, 0, 0], 'Stalling must demote to the easier level'
env.common_step_counter = 0
robot.data.root_link_pos_w[1, 0] = 5
terrain_levels_vel(env, ids, 'twist')
assert terrain.terrain_levels.tolist() == [0, 0, 0, 0], 'Initial reset must not manufacture progression'
print('PASS native terrain tensors: sparse promotion, mean/max logging, demotion and initial reset')
