"""Describe generated values without repairing them or claiming feasibility."""
import math


def annotate(value):
    results = []
    width, height = value['scene']['world_size']
    for trace in value.get('referenceFlow', []):
        paths = []
        for path in trace['states'][-1]:
            poses = path['poses']
            length = sum(math.dist(a[:2], b[:2]) for a, b in zip(poses, poses[1:]))
            displacement = math.dist(poses[0][:2], poses[-1][:2])
            outside = sum(not (0 <= p[0] <= width and 0 <= p[1] <= height) for p in poses)
            paths.append({'object': path['object'], 'lengthMeters': round(length, 3),
                          'displacementMeters': round(displacement, 3),
                          'outsideWorldWaypoints': outside})
        results.append({'seed': trace['seed'], 'paths': paths})
    value['diagnostics'] = {
        'endToEndSelectedCounts': [sum(trace['selected']) for trace in value['traces']],
        'conditionalDraws': results,
        'scope': 'Raw predicted path measurements. World bounds are a necessary check, not a collision or execution certificate.'}
    return value
