"""Numeric geometry conversion. No source names or paths are exported."""
import trimesh

def mesh(m,i):
 t=int(m.geom_type[i]);s=m.geom_size[i]
 if t==7:
  mid=m.geom_dataid[i];v=m.mesh_vertadr[mid];nv=m.mesh_vertnum[mid];f=m.mesh_faceadr[mid];nf=m.mesh_facenum[mid]
  return trimesh.Trimesh(vertices=m.mesh_vert[v:v+nv].copy(),faces=m.mesh_face[f:f+nf].copy(),process=False)
 if t==6:return trimesh.creation.box(extents=2*s)
 if t==2:return trimesh.creation.icosphere(subdivisions=2,radius=s[0])
 if t==3:return trimesh.creation.capsule(radius=s[0],height=2*s[1],count=[12,12])
 if t==5:return trimesh.creation.cylinder(radius=s[0],height=2*s[1],sections=24)
 if t==4:
  a=trimesh.creation.icosphere(subdivisions=2);a.vertices*=s;return a
 if t==0:return trimesh.creation.box(extents=[max(2*s[0],24),max(2*s[1],24),.02])
 raise ValueError(f'Unsupported geom type {t}')
def add(server,name,t,position=(0,0,0),wxyz=(1,0,0,0),color=(170,175,180)):
 return server.scene.add_mesh_simple(name,vertices=t.vertices,faces=t.faces,position=position,wxyz=wxyz,color=color,flat_shading=False)
