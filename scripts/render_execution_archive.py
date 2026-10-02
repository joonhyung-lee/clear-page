"""Render two synchronized cameras from numeric Viser meshes and recorded poses.

MuJoCo is used only as a rasterizer. Mocap bodies receive archived transforms,
with linear translation and quaternion SLERP between measurements. No physics
step, controller update, or extrapolation is performed.
"""
import argparse
from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import mujoco
import imageio_ffmpeg
from PIL import Image
from scipy.spatial.transform import Rotation, Slerp
from recording_io import read_recording

ROOT = Path(__file__).resolve().parents[1]


def numbers(values):
    return ' '.join(str(float(x)) for x in values)


class ArchiveRenderer:
    def __init__(self, scene, chase=False):
        self.chase = chase
        self.record, self.buffers = read_recording(ROOT / f'assets/recordings/{scene}.viser')
        self.nodes = defaultdict(lambda: dict(props={}, position=np.zeros(3), wxyz=[1, 0, 0, 0], visible=True))
        self.cursor = 0
        self.tracks = defaultdict(dict)
        for t, m in self.record['messages']:
            if m['type'] in ('SetPositionMessage', 'SetOrientationMessage'):
                field = 'position' if m['type'] == 'SetPositionMessage' else 'wxyz'
                self.tracks[(m['name'], field)][t] = m[field]
        self.sample = {}
        for key, values in self.tracks.items():
            times = np.array(sorted(values))
            data = np.array([values[t] for t in times])
            if key[1] == 'wxyz' and len(times) > 1:
                interp = Slerp(times, Rotation.from_quat(data, scalar_first=True))
                self.sample[key] = lambda t, ts=times, fn=interp: fn(np.clip(t, ts[0], ts[-1])).as_quat(scalar_first=True)
            else:
                self.sample[key] = lambda t, ts=times, d=data: np.array([np.interp(t, ts, d[:, k]) for k in range(d.shape[1])])
        self.seek_messages(0.)
        xml = ET.Element('mujoco')
        ET.SubElement(xml, 'compiler', angle='radian')
        visual = ET.SubElement(xml, 'visual')
        ET.SubElement(visual, 'global', offwidth='640', offheight='480')
        ET.SubElement(visual, 'headlight', ambient='.65 .65 .65', diffuse='.35 .35 .35', specular='0 0 0')
        ET.SubElement(visual, 'map', znear='.005')
        asset = ET.SubElement(xml, 'asset')
        ET.SubElement(asset, 'texture', type='skybox', builtin='flat', rgb1='1 1 1', width='64', height='64')
        world = ET.SubElement(xml, 'worldbody')
        ET.SubElement(world, 'light', pos='0 0 10', dir='0 0 -1', directional='true', diffuse='.25 .25 .25', castshadow='false')
        bodies = {}
        mesh_assets = {}
        for name, node in list(self.nodes.items()):
            if node.get('type') != 'MeshMessage' or '/body-' not in name:
                continue
            parent = name.rsplit('/', 1)[0]
            if parent not in bodies:
                bodies[parent] = ET.SubElement(world, 'body', name=parent, mocap='true')
            props = node['props']
            vertices, faces = self.array(props['vertices']), self.array(props['faces'])
            file = f'mesh-{len(mesh_assets)}.obj'
            mesh_assets[file] = ('\n'.join('v '+numbers(v) for v in vertices)+'\n'+
                                 '\n'.join('f '+' '.join(str(int(x)+1) for x in f) for f in faces)).encode()
            ET.SubElement(asset, 'mesh', name=file, file=file, inertia='shell')
            rgba = [x/255 for x in props['color']] + [props.get('opacity') or 1.]
            ET.SubElement(bodies[parent], 'geom', type='mesh', mesh=file,
                          pos=numbers(node['position']), quat=numbers(node['wxyz']),
                          rgba=numbers(rgba), contype='0', conaffinity='0')
        # Fixed cameras use the renderer's projection, including the true aspect ratio.
        view = ET.SubElement(world, 'body', name='main-camera-body', mocap='true')
        camera = {}
        for _, m in self.record['messages']:
            if m['type'] in ('SetCameraPositionMessage', 'SetCameraLookAtMessage', 'SetCameraFovMessage'):
                camera.update(m)
        eye = np.array(camera['position'])
        look_at = np.array(camera['look_at'])
        if chase:
            initial = np.array(self.nodes['/body-1']['position']); initial[2] = 0
            eye = initial + [-2.6, -1.8, 2.4]
            look_at = initial + [.6, 0, .7]
            camera['fov'] = .85
        forward = look_at-eye
        forward /= np.linalg.norm(forward)
        right = np.cross(forward, [0., 0., 1.]); right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        ET.SubElement(view, 'camera', name='main', pos=numbers(eye), xyaxes=numbers(np.r_[right, up]), fovy=str(camera['fov']*180/np.pi))
        self.prefix = '/tracking' if '/tracking/body-16' in bodies else ''
        ET.SubElement(bodies[self.prefix+'/body-16'], 'camera', name='ego', pos='.14 0 .30', xyaxes='0 -1 0 0 0 1', fovy='60')
        self.model = mujoco.MjModel.from_xml_string(ET.tostring(xml, encoding='unicode'), assets=mesh_assets)
        self.data = mujoco.MjData(self.model)
        self.body_ids = {name: self.model.body(name).mocapid[0] for name in bodies}
        self.camera_id = self.model.body('main-camera-body').mocapid[0]
        self.renderer = mujoco.Renderer(self.model, height=480, width=640, max_geom=10000)

    def array(self, ref):
        return np.frombuffer(self.buffers[ref['__binary_index']], dtype=ref['dtype']).reshape(-1, 3)

    def seek_messages(self, time):
        messages = self.record['messages']
        while self.cursor < len(messages) and messages[self.cursor][0] <= time+1e-8:
            _, m = messages[self.cursor]; self.cursor += 1
            if 'name' not in m:
                continue
            node = self.nodes[m['name']]
            kind = m['type']
            if 'props' in m:
                node['props'] = m['props'].copy(); node['type'] = kind
            elif kind == 'SceneNodeUpdateMessage':
                node['props'].update(m['updates'])
            elif kind == 'SetPositionMessage':
                node['position'] = m['position']
            elif kind == 'SetOrientationMessage':
                node['wxyz'] = m['wxyz']
            elif kind == 'SetSceneNodeVisibilityMessage':
                node['visible'] = m['visible']

    def visible(self, name):
        while name and name != '/tracking':
            if not self.nodes[name]['visible']:
                return False
            name = name.rsplit('/', 1)[0]
        return True

    def world_points(self, name, points):
        # Published annotations use world coordinates below /tracking. Ignore its
        # display-only chase transform because these cameras already follow the body.
        while name and name != '/tracking':
            node = self.nodes[name]
            points = Rotation.from_quat(node['wxyz'], scalar_first=True).apply(points)+node['position']
            name = name.rsplit('/', 1)[0]
        return points

    def draw_annotations(self):
        scene = self.renderer.scene
        for name, node in list(self.nodes.items()):
            kind = node.get('type')
            # Viser uses flat billboard rims. Concentric solid spheres would
            # hide their colored cores in this mesh rasterizer.
            if kind not in ('LineSegmentsMessage', 'PointCloudMessage') or name.endswith('-outline') or not self.visible(name):
                continue
            props = node['props']; points = self.world_points(name, self.array(props['points']))
            colors = self.array(props['colors']) / 255
            if kind == 'LineSegmentsMessage':
                for i, (start, end) in enumerate(points.reshape(-1, 2, 3)):
                    if np.linalg.norm(end-start) < 1e-6:
                        continue
                    geom = scene.geoms[scene.ngeom]
                    color = colors[min(i*2, len(colors)-1)]
                    mujoco.mjv_initGeom(geom, mujoco.mjtGeom.mjGEOM_CAPSULE, np.zeros(3), np.zeros(3), np.eye(3).ravel(), np.r_[color, .7])
                    mujoco.mjv_connector(geom, mujoco.mjtGeom.mjGEOM_CAPSULE, max(.002, props['line_width']*.0018), start, end)
                    scene.ngeom += 1
            else:
                for i, pos in enumerate(points):
                    geom = scene.geoms[scene.ngeom]
                    radius = props['point_size']/2
                    mujoco.mjv_initGeom(geom, mujoco.mjtGeom.mjGEOM_SPHERE, np.full(3, radius), pos, np.eye(3).ravel(), np.r_[colors[min(i, len(colors)-1)], 1.])
                    scene.ngeom += 1

    def frame(self, t, ego=False):
        self.seek_messages(t)
        for (name, field), sample in self.sample.items():
            if name in self.body_ids:
                value = sample(t)
                target = self.data.mocap_pos if field == 'position' else self.data.mocap_quat
                target[self.body_ids[name]] = value
        # Invert the archive's display-only chase transform for a world camera.
        if self.chase:
            base = self.sample[(self.prefix+'/body-1', 'position')](t).copy()
            initial = self.sample[(self.prefix+'/body-1', 'position')](0).copy()
            base[2] = initial[2] = 0
            self.data.mocap_pos[self.camera_id] = base-initial
            self.data.mocap_quat[self.camera_id] = [1,0,0,0]
        elif ('/tracking', 'position') in self.sample:
            orientation = self.sample.get(('/tracking', 'wxyz'), lambda t: [1, 0, 0, 0])
            rotation = Rotation.from_quat(orientation(t), scalar_first=True).inv()
            self.data.mocap_pos[self.camera_id] = -rotation.apply(self.sample[('/tracking', 'position')](t))
            self.data.mocap_quat[self.camera_id] = rotation.as_quat(scalar_first=True)
        mujoco.mj_forward(self.model, self.data)
        self.renderer.update_scene(self.data, camera='ego' if ego else 'main')
        if not ego:
            self.draw_annotations()
        pixels = self.renderer.render()
        return np.array(Image.fromarray(pixels).resize((480, 360), Image.Resampling.LANCZOS)) if ego else pixels


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene', default='mpc-optimized-full')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--sample', type=float)
    p.add_argument('--fps', type=int, default=30)
    p.add_argument('--duration', type=float, default=40.)
    p.add_argument('--chase', action='store_true')
    args = p.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    if args.fps <= 0 or args.duration <= 0:
        p.error('fps and duration must be positive')
    renderer = ArchiveRenderer(args.scene, chase=args.chase)
    writers = {}
    frames = [args.sample] if args.sample is not None else np.arange(round(args.duration*args.fps))/args.fps
    try:
        for i, t in enumerate(frames):
            for ego in (False, True):
                suffix = 'ego' if ego else 'contact'
                pixels = renderer.frame(float(t), ego)
                if args.sample is not None or i % 300 == 0:
                    Image.fromarray(pixels).save(args.output / f'{args.scene}-{suffix}-{t:g}.png')
                if args.sample is None:
                    if ego not in writers:
                        path = args.output / f'{args.scene}-{suffix}.mp4'
                        writer = imageio_ffmpeg.write_frames(str(path), (pixels.shape[1], pixels.shape[0]), fps=args.fps, codec='libx264', macro_block_size=1,
                            output_params=['-crf','19','-map_metadata','-1','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart'])
                        writer.send(None); writers[ego] = writer
                    writers[ego].send(pixels)
            if i % 150 == 0:
                print(f'{args.scene}: paired frame {i}/{len(frames)}', flush=True)
    finally:
        for writer in writers.values():
            writer.close()
        renderer.renderer.close()


if __name__ == '__main__':
    main()
