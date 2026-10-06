"""Conditional attention distribution over object identities and terrain class."""
import numpy as np

def distribution(weights,keys):
    weights=np.asarray(weights,dtype=float)
    if not np.isfinite(weights).all() or (weights<0).any():raise ValueError('Invalid attention weights')
    indices=[i for i,k in enumerate(keys) if k['kind']=='object']
    terrain=[i for i,k in enumerate(keys) if k['kind']=='terrain']
    mass=np.array([weights[i] for i in indices]+[weights[terrain].sum()])
    if mass.sum()<=0:raise ValueError('No object or terrain attention mass')
    probability=mass/mass.sum()
    labels=[keys[i]['source_id'].replace('object:','Object ') for i in indices]+['Terrain']
    # Largest-remainder rounding ensures even the displayed decimals sum to 1.
    units=np.floor(probability*1000).astype(int)
    for i in np.argsort(-(probability*1000-units),kind='stable')[:1000-units.sum()]:units[i]+=1
    colors=np.zeros(len(weights))
    for i,p in zip(indices,probability[:-1]):colors[i]=p
    # The legend groups terrain mass; each surface keeps its own token mass.
    colors[terrain]=weights[terrain]/mass.sum()
    return labels,probability,units,colors
