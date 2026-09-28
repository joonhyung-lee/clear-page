"""Conservative planar clearance checks for an explanatory display refinement.

This is separate from learned generation. It checks bounding discs against walls,
other object footprints, and the observed robot footprint, not dynamic execution.
"""
import heapq
import numpy as np
from shapely.geometry import LineString,box

class Clearance:
 def __init__(self,scene,object_id,placed=None):
  self.scene=scene;self.own=object_id;self.radius=np.linalg.norm(scene['objects'][object_id]['size'][:2])/2+.025
  self.walls=[box(*w) for w in scene['walls']]
  self.obstacles=[]
  for o in scene['objects']:
   if o['object_id']==object_id:continue
   center=(placed or {}).get(o['object_id'],o['pose'][:2])
   self.obstacles.append((np.asarray(center),np.linalg.norm(o['size'][:2])/2))
  self.obstacles.append((np.asarray(scene['start'][:2]),.35))
 def free(self,points):
  p=np.atleast_2d(points);ok=np.ones(len(p),bool)
  for x0,y0,x1,y1 in self.scene['walls']:
   nearest=np.clip(p,[x0,y0],[x1,y1]);ok&=np.sum((p-nearest)**2,axis=1)>self.radius**2
  for c,r in self.obstacles:ok&=np.sum((p-c)**2,axis=1)>(r+self.radius)**2
  return ok
 def segment(self,a,b):
  a=np.asarray(a);b=np.asarray(b);delta=b-a;length2=float(delta@delta)
  if length2<1e-18:return bool(self.free(a)[0])
  line=LineString([a,b])
  if any(line.distance(wall)<=self.radius for wall in self.walls):return False
  for center,r in self.obstacles:
   t=np.clip(float((center-a)@delta)/length2,0,1)
   if np.linalg.norm(center-(a+t*delta))<=r+self.radius:return False
  return True
 def project(self,p):
  if self.free(p)[0]:return np.asarray(p)
  theta=np.linspace(0,2*np.pi,128,endpoint=False);rays=np.column_stack([np.cos(theta),np.sin(theta)])
  for r in np.arange(.025,3,.025):
   candidates=np.asarray(p)+r*rays;valid=self.free(candidates)
   if valid.any():return candidates[np.flatnonzero(valid)[0]]
  raise ValueError('No nearby collision-free projection')
 def connect(self,a,b):
  if self.segment(a,b):return [a,b]
  resolution=.1;world=np.asarray(self.scene['world_size'])/resolution
  def snap(point):
   center=np.rint(np.asarray(point)/resolution).astype(int)
   for radius in range(6):
    candidates=[tuple(center+[dx,dy]) for dx in range(-radius,radius+1) for dy in range(-radius,radius+1)]
    candidates.sort(key=lambda k:np.linalg.norm(np.asarray(k)*resolution-point))
    for candidate in candidates:
     if min(candidate)>=0 and all(np.asarray(candidate)<=world) and self.segment(point,np.asarray(candidate)*resolution):return candidate
   raise ValueError('No visible free grid cell near endpoint')
  start=snap(a);goal=snap(b)
  heap=[(0.,start)];cost={start:0.};parent={};found=False
  while heap:
   _,u=heapq.heappop(heap)
   if u==goal:found=True;break
   for dx,dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
    v=(u[0]+dx,u[1]+dy)
    if min(v)<0 or any(np.asarray(v)>world):continue
    if not self.segment(np.asarray(u)*resolution,np.asarray(v)*resolution):continue
    score=cost[u]+np.hypot(dx,dy)
    if score<cost.get(v,float('inf')):
     cost[v]=score;parent[v]=u;heapq.heappush(heap,(score+np.linalg.norm(np.asarray(v)-goal),v))
  if not found:raise ValueError('No collision-free connection')
  route=[goal]
  while route[-1]!=start:route.append(parent[route[-1]])
  route=[np.asarray(a),*[np.asarray(v)*resolution for v in route[::-1]],np.asarray(b)]
  if not all(self.segment(x,y) for x,y in zip(route,route[1:])):raise ValueError('Grid endpoint connection invalid')
  return route
 def refine(self,poses):
  raw=np.asarray(poses,dtype=float);xy=np.asarray([self.project(p) for p in raw[:,:2]])
  # Smooth while keeping endpoints and accepting only free adjacent segments.
  for _ in range(18):
   for i in range(1,len(xy)-1):
    candidate=.2*raw[i,:2]+.4*(xy[i-1]+xy[i+1])
    if self.free(candidate)[0] and self.segment(xy[i-1],candidate) and self.segment(candidate,xy[i+1]):xy[i]=candidate
  connected=[xy[0]]
  for p in xy[1:]:connected.extend(self.connect(connected[-1],p)[1:])
  connected=np.asarray(connected)
  assert all(self.segment(x,y) for x,y in zip(connected,connected[1:]))
  return connected
