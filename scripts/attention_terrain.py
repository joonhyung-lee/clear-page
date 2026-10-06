"""Semantic terrain colors and geometry cues, independent of attention scores."""
import numpy as np
from PIL import Image,ImageDraw

PALETTE={'ramp':(235,204,165),'stair_tread':(164,198,220),'flat':(206,195,219)}
LABELS={'ramp':'Ramp','stair_tread':'Step','flat':'Platform'}

def terrain_color(tile):
    return PALETTE[tile['kind']]

def height(tile,x,y):
    if tile['kind']!='ramp':return tile['height_m']
    axis=tile['axis'];lo=tile['bounds'][axis];hi=tile['bounds'][axis+2]
    u=np.clip(((x,y)[axis]-lo)/(hi-lo),0,1)
    return tile['start_height_m']+u*(tile['end_height_m']-tile['start_height_m'])

def features(tile):
    """True top boundary/risers, ramp contours and an uphill direction arrow."""
    l,b,r,u=tile['bounds'];xy=[(l,b),(r,b),(r,u),(l,u)]
    corners=[(x,y,height(tile,x,y)+.015) for x,y in xy]
    borders=[(corners[i],corners[(i+1)%4]) for i in range(4)]
    risers=[((x,y,.01),p) for (x,y),p in zip(xy,corners) if p[2]>.03]
    contours=[];arrow=[]
    if tile['kind']=='ramp':
        axis=tile['axis']
        for f in [.25,.5,.75]:
            ends=[(l+(r-l)*f,b),(l+(r-l)*f,u)] if axis==0 else [(l,b+(u-b)*f),(r,b+(u-b)*f)]
            contours.append(tuple((x,y,height(tile,x,y)+.02) for x,y in ends))
        center=np.array([(l+r)/2,(b+u)/2]);direction=np.zeros(2)
        direction[axis]=np.sign(tile['end_height_m']-tile['start_height_m'])
        length=(r-l if axis==0 else u-b)*.36
        a=center-direction*length/2;z=center+direction*length/2
        side=np.array([-direction[1],direction[0]])
        arrow=[(a,z),(z,z-direction*length*.30+side*length*.20),(z,z-direction*length*.30-side*length*.20)]
        arrow=[tuple((float(p[0]),float(p[1]),height(tile,*p)+.025) for p in pair) for pair in arrow]
    return borders,risers,contours,arrow

def draw_terrain(image,camera,rect,tiles,probabilities):
    x0,y0,width,screen_height=rect
    layer=Image.new('RGBA',(width,screen_height));draw=ImageDraw.Draw(layer)
    def segment(a,b,color,weight):
        a=camera@np.r_[a,1.];b=camera@np.r_[b,1.]
        for axis in range(3):
            for sign in [-1,1]:
                fa=a[3]+sign*a[axis];fb=b[3]+sign*b[axis]
                if fa<0 and fb<0:return
                if fa<0:a=a+(b-a)*fa/(fa-fb)
                elif fb<0:b=b+(a-b)*fb/(fb-fa)
        if min(a[3],b[3])<=0:return
        points=[((p[0]/p[3]+1)*width/2,(1-p[1]/p[3])*screen_height/2) for p in [a,b]]
        draw.line(points,fill=color,width=weight)
    for tile,prob in zip(tiles,probabilities,strict=True):
        borders,risers,contours,arrow=features(tile)
        # Green contour opacity is linear in this token's normalized mass.
        for a,b in borders:segment(a,b,(0,105,60,round(255*prob)),10)
        for a,b in borders:segment(a,b,(63,78,79,200),2)
        for a,b in risers:segment(a,b,(63,78,79,150),2)
        for a,b in contours:segment(a,b,(91,86,74,135),1)
        for a,b in arrow:segment(a,b,(75,68,56,220),2)
    image.paste(layer,(x0,y0),layer)

def draw_minimap_terrain(draw,project,tiles,probabilities):
    for tile,prob in zip(tiles,probabilities,strict=True):
        l,b,r,u=tile['bounds'];draw.rectangle([project((l,u)),project((r,b))],fill=terrain_color(tile),outline='#526667',width=1)
        borders,_,contours,arrow=features(tile)
        for a,z in contours:draw.line([project(a),project(z)],fill='#a59680',width=1)
        for a,z in arrow:draw.line([project(a),project(z)],fill='#554c3e',width=1)
        # A small green segment shows actual token mass; semantics keep their color.
        draw.line([project((l,u)),project((l+(r-l)*prob,u))],fill='#087447',width=2)

def profile_tiles(tiles,position):
    """Select the closest terrain band without changing its metric geometry."""
    nearest=min(tiles,key=lambda t:max(t['bounds'][1]-position[1],0,position[1]-t['bounds'][3]))
    return [t for t in tiles if np.allclose(np.asarray(t['bounds'])[[1,3]],np.asarray(nearest['bounds'])[[1,3]])]

def draw_profile(draw,tiles,position,world,fonts):
    active=profile_tiles(tiles,position)
    bands={}
    for tile in tiles:bands.setdefault(tuple(np.asarray(tile['bounds'])[[1,3]]),[]).append(tile)
    draw.rounded_rectangle((288,422,562,704),radius=7,fill=(250,251,248),outline='#b9c8be')
    draw.text((302,434),'Terrain profiles',font=fonts[17],fill='#24332e')
    ymax=max(max(height(t,x,y) for x in [t['bounds'][0],t['bounds'][2]] for y in [t['bounds'][1],t['bounds'][3]]) for t in tiles)
    for index,((b,u),band) in enumerate(sorted(bands.items())):
        base=514+index*78
        def project(x,z):return (338+205*x/world[0],base-34*z/ymax)
        draw.text((302,base-55),f'y = {(b+u)/2:g} m',font=fonts[13],fill='#56655c')
        if band==active:draw.line((302,base-51,302,base-3),fill='#243b52',width=3)
        for z in [0,ymax]:
            py=project(0,z)[1]
            draw.line((338,py,543,py),fill='#dfe5df',width=1)
            draw.text((309,py-7),f'{z:g}',font=fonts[13],fill='#56655c')
        for tile in band:
            l,_,r,_=tile['bounds'];y=(b+u)/2
            points=[project(l,0),project(l,height(tile,l,y)),project(r,height(tile,r,y)),project(r,0)]
            draw.polygon(points,fill=terrain_color(tile))
            draw.line(points+[points[0]],fill='#526667',width=2)
    draw.text((305,686),'Height (m)',font=fonts[13],fill='#56655c')
    draw.text((433,686),f'x: 0–{world[0]:g} m',font=fonts[13],fill='#56655c')
