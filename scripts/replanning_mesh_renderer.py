"""Offscreen views of the same numeric meshes and poses as the Viser replay."""
import ctypes
import numpy as np
import mujoco
from OpenGL import GL
from OpenGL.GL.shaders import compileProgram, compileShader

class MeshRenderer:
    def __init__(self, geometry, meshes, width=1280, height=720):
        self.meshes = meshes
        self.width, self.height = width, height
        self.context = mujoco.GLContext(width, height)
        self.context.make_current()
        self.fbo = GL.glGenFramebuffers(1)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo)
        self.buffers = GL.glGenRenderbuffers(2)
        for buffer, format, attachment in zip(self.buffers, [GL.GL_RGBA8, GL.GL_DEPTH_COMPONENT24],
                                              [GL.GL_COLOR_ATTACHMENT0, GL.GL_DEPTH_ATTACHMENT]):
            GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, buffer)
            GL.glRenderbufferStorage(GL.GL_RENDERBUFFER, format, width, height)
            GL.glFramebufferRenderbuffer(GL.GL_FRAMEBUFFER, attachment, GL.GL_RENDERBUFFER, buffer)
        assert GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) == GL.GL_FRAMEBUFFER_COMPLETE
        self.program = compileProgram(compileShader('''#version 330
layout(location=0) in vec3 vertex; layout(location=1) in vec3 normal;
uniform mat4 mvp; uniform mat4 model; out vec3 n;
void main(){gl_Position=mvp*vec4(vertex,1);n=mat3(model)*normal;}
''', GL.GL_VERTEX_SHADER), compileShader('''#version 330
in vec3 n; uniform vec3 color; out vec4 pixel;
void main(){float s=.72+.28*abs(dot(normalize(n),normalize(vec3(.25,-.35,1))));pixel=vec4(color*s,1);}
''', GL.GL_FRAGMENT_SHADER))
        self.uniforms = {k: GL.glGetUniformLocation(self.program, k) for k in ['mvp', 'model', 'color']}
        self.gpus = []
        for i in range(len(meshes)):
            v = np.c_[geometry[f'vertices_{i}'], geometry[f'normals_{i}']].astype('f4')
            faces = geometry[f'faces_{i}'].astype('u4')
            vao = GL.glGenVertexArrays(1)
            GL.glBindVertexArray(vao)
            vbo, ebo = GL.glGenBuffers(2)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
            GL.glBufferData(GL.GL_ARRAY_BUFFER, v.nbytes, v, GL.GL_STATIC_DRAW)
            for k in range(2):
                GL.glEnableVertexAttribArray(k)
                GL.glVertexAttribPointer(k, 3, GL.GL_FLOAT, False, 24, ctypes.c_void_p(k*12))
            GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, ebo)
            GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, faces.nbytes, faces, GL.GL_STATIC_DRAW)
            self.gpus.append((vao, vbo, ebo, faces.size))

    def render(self, matrices, camera, width, height, colors=None, hide=()):
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo)
        GL.glViewport(0, 0, width, height)
        GL.glClearColor(.975, .982, .971, 1)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glUseProgram(self.program)
        for i, (mesh, gpu) in enumerate(zip(self.meshes, self.gpus, strict=True)):
            if mesh['body'] in hide:
                continue
            matrix = matrices[mesh['body']]
            for key, value in [('mvp', camera@matrix), ('model', matrix)]:
                GL.glUniformMatrix4fv(self.uniforms[key], 1, True, np.asarray(value, dtype='f4'))
            color = np.asarray(mesh['color'])/255 if colors is None else colors[i]
            GL.glUniform3fv(self.uniforms['color'], 1, np.asarray(color, dtype='f4'))
            GL.glBindVertexArray(gpu[0])
            GL.glDrawElements(GL.GL_TRIANGLES, gpu[3], GL.GL_UNSIGNED_INT, None)
        return np.frombuffer(GL.glReadPixels(0, 0, width, height, GL.GL_RGB, GL.GL_UNSIGNED_BYTE),
                             dtype='u1').reshape(height, width, 3)[::-1].copy()

    def close(self):
        for vao, vbo, ebo, _ in self.gpus:
            GL.glDeleteVertexArrays(1, [vao])
            GL.glDeleteBuffers(2, [vbo, ebo])
        GL.glDeleteProgram(self.program)
        GL.glDeleteRenderbuffers(2, self.buffers)
        GL.glDeleteFramebuffers(1, [self.fbo])
        self.context.free()

def camera_matrix(eye, target, aspect, extent=None, fov=65):
    eye, target = np.asarray(eye, float), np.asarray(target, float)
    forward = target-eye
    forward /= np.linalg.norm(forward)
    world_up = np.array([0., 0., 1.]) if abs(forward[2]) < .99 else np.array([0., 1., 0.])
    right = np.cross(forward, world_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    view = np.eye(4)
    view[:3, :3] = [right, up, -forward]
    view[:3, 3] = -view[:3, :3]@eye
    if extent is not None:
        projection = np.diag([2/(extent*aspect), 2/extent, -2/100, 1.])
        projection[2, 3] = -1
    else:
        f = 1/np.tan(np.deg2rad(fov)/2)
        near, far = .05, 100.
        projection = np.array([[f/aspect, 0, 0, 0], [0, f, 0, 0],
                               [0, 0, -(far+near)/(far-near), -2*far*near/(far-near)], [0, 0, -1, 0]])
    return projection@view
