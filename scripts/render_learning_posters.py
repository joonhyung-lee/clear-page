"""Render opaque checkpoint thumbnails from the published mesh and camera data.

CPU depth rendering makes this usable without a browser or a display server.
The interactive viewer remains the native Viser replay.
"""
import argparse
import json
import tempfile
from pathlib import Path
import numpy as np
from numba import njit
from PIL import Image
from scipy.spatial.transform import Rotation
from recording_io import read_recording


@njit
def raster(points, faces, shades, depth, pixels, color):
    height, width = depth.shape
    for i in range(len(faces)):
        a, b, c = points[faces[i, 0]], points[faces[i, 1]], points[faces[i, 2]]
        if min(a[2], b[2], c[2]) <= .1:
            continue
        xmin, xmax = max(0, int(np.floor(min(a[0], b[0], c[0])))), min(width-1, int(np.ceil(max(a[0], b[0], c[0]))))
        ymin, ymax = max(0, int(np.floor(min(a[1], b[1], c[1])))), min(height-1, int(np.ceil(max(a[1], b[1], c[1]))))
        area = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(area) < 1e-8:
            continue
        for y in range(ymin, ymax+1):
            for x in range(xmin, xmax+1):
                u = ((b[1]-c[1])*(x+.5-c[0])+(c[0]-b[0])*(y+.5-c[1]))/area
                v = ((c[1]-a[1])*(x+.5-c[0])+(a[0]-c[0])*(y+.5-c[1]))/area
                w = 1-u-v
                if min(u, v, w) < 0:
                    continue
                z = 1/(u/a[2]+v/b[2]+w/c[2])
                if z < depth[y, x]:
                    depth[y, x] = z
                    for k in range(3):
                        pixels[y, x, k] = min(255, color[k]*shades[i])


def render(body, size=1000, scene=None, recordings_dir=None, output_dir=None):
    root = Path(__file__).resolve().parents[1]
    scene = scene or f'learning-{body}'
    text = ((recordings_dir or root / 'assets/recordings') / f'{scene}.hex.js').read_text()
    with tempfile.NamedTemporaryFile(suffix='.viser') as tmp:
        tmp.write(bytes.fromhex(json.loads(text.rsplit(' = ', 1)[1].rstrip(';\n'))))
        tmp.flush()
        record, buffers = read_recording(tmp.name)
    camera = {}
    for _, message in record['messages']:
        if message['type'] in ['SetCameraPositionMessage', 'SetCameraLookAtMessage', 'SetCameraFovMessage']:
            camera.update(message)
    eye, target, fov = np.array(camera['position']), np.array(camera['look_at']), camera['fov']
    forward = target-eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0, 0, 1.])
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    basis = np.stack([right, up, forward], axis=1)
    focal = size / (2*np.tan(fov/2))
    depth = np.full((size, size), np.inf)
    pixels = np.full((size, size, 3), 248., dtype=np.float64)
    light = np.array([.2, -.5, 1.])
    light /= np.linalg.norm(light)

    def array(ref, dtype, width=3):
        return np.frombuffer(buffers[ref['__binary_index']], dtype=dtype).reshape(-1, width)

    def draw(vertices, faces, color, ambient=.48):
        local = (vertices-eye) @ basis
        projected = np.column_stack([size/2+local[:, 0]/local[:, 2]*focal,
                                     size/2-local[:, 1]/local[:, 2]*focal, local[:, 2]])
        triangle = vertices[faces]
        normal = np.cross(triangle[:, 1]-triangle[:, 0], triangle[:, 2]-triangle[:, 0])
        normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
        shade = ambient + (1-ambient)*np.abs(normal @ light)
        raster(projected, faces, shade, depth, pixels, np.asarray(color, dtype=float))

    for _, message in record['messages']:
        if message['type'] not in ['MeshMessage', 'BatchedMeshesMessage']:
            continue
        p = message['props']
        vertices, faces = array(p['vertices'], '<f4'), array(p['faces'], '<u4')
        if message['type'] == 'MeshMessage':
            draw(vertices, faces, p['color'], ambient=.86)
        else:
            colors = array(p['batched_colors'], 'u1')
            for index, (pos, quat) in enumerate(zip(array(p['batched_positions'], '<f4'), array(p['batched_wxyzs'], '<f4', 4))):
                # Only bodies intersecting the camera frustum need rasterization.
                center = (pos-eye) @ basis
                margin = 2.
                if center[2] < -margin or np.any(np.abs(center[:2]) > max(center[2], 0)*np.tan(fov/2)+margin):
                    continue
                draw(Rotation.from_quat(quat, scalar_first=True).apply(vertices)+pos, faces, colors[min(index, len(colors)-1)])
    out = (output_dir or root / 'assets/media') / f'{scene}.png'
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels.astype('uint8')).resize((700, 700), Image.Resampling.LANCZOS).save(out)
    print(body, 'poster rendered from published complete mesh')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body', choices=['g1', 'spot', 'spot_arm'], required=True)
    parser.add_argument('--scene')
    parser.add_argument('--recordings-dir', type=Path)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    render(args.body, scene=args.scene, recordings_dir=args.recordings_dir, output_dir=args.output_dir)
