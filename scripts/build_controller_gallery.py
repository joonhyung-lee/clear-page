"""Build task galleries from recorded outcomes, preserving unavailable results."""
import json
from pathlib import Path
from bs4 import BeautifulSoup

root = Path(__file__).resolve().parents[1]
rows = json.loads((root/'assets/controller-gallery.json').read_text())
soup = BeautifulSoup((root/'index.html').read_text(), 'html.parser')


def tag(name, text=None, **attrs):
    node = soup.new_tag(name, attrs=attrs)
    if text is not None:
        node.string = text
    return node


def gallery(controller, label, group):
    section = tag('section', **{'class': 'controller-gallery', 'data-controller': controller})
    section.append(tag('h4', label))
    grid = tag('div', **{'class': 'media-grid', 'data-grid': f'controller-{group}-{controller}',
                        'aria-label': f'{label} task replays'})
    section.append(grid)
    order = ['G1', 'Spot + arm', 'Table Push', 'Chair Push', 'Door Open', 'Box Push', 'Gate Push']
    items = sorted([r for r in rows if r['controller'] == controller and r['group'] == group],
                   key=lambda r: order.index(r['task']))
    for row in items:
        if row['scene'] is None:
            tile = tag('div', **{'class': 'media-unavailable'})
            tile.append(tag('span', row['task']))
            tile.append(tag('small', row['outcome']))
            if row['note']:
                tile['title'] = row['note']
                tile['aria-label'] = row['task']+'. '+row['outcome']+'. '+row['note']
            grid.append(tile)
            continue
        scene = row['scene']
        outcome=('Incomplete · ' if row.get('interactionComplete') is False else '')+row['outcome']
        for path in [f'media/{scene}.png', f'media/{scene}.mp4', f'recordings/{scene}.hex.js']:
            assert (root/'assets'/path).is_file(), f'Missing published asset: {path}'
        tile = tag('button', type='button', **{'class': 'media-tile', 'data-scene': scene,
                    'data-title': f"{row['task']} · {label}", 'data-note': row['note'],
                    'data-outcome': outcome, 'aria-label': f"Expand {row['task']}, {label}"})
        if row.get('variant'):
            tile['data-title']=row['task']+' · '+row['variant']
        video = tag('video', loop='', muted='', playsinline='', preload='none',
                    poster=f'assets/media/{scene}.png', **{'data-autoplay': ''})
        video.append(tag('source', src=f'assets/media/{scene}.mp4', type='video/mp4'))
        tile.append(video)
        tile.append(tag('span', row['task']))
        tile.append(tag('small', outcome))
        if row.get('variant'):
            tile.append(tag('small', row['variant'], **{'class':'controller-variant'}))
        grid.append(tile)
    for row in items:
        if row.get('originalScene'):
            link=tag('a','Original MPC recording' if row.get('costAblation') else 'Original shaped-command recording',href=f"assets/media/{row['originalScene']}.mp4",
                     target='_blank',rel='noopener',**{'class':'original-recording'})
            section.append(link)
    overlay = BeautifulSoup('''<div class="grid-focus" hidden><div class="viewer focus-viewer"
        data-generation="true" data-scene=""><video controls muted playsinline preload="none"></video>
        <button class="launch" type="button">Play in 3D</button></div><span class="focus-title"></span>
        <button class="focus-close" type="button" aria-label="Close enlarged preview">×</button>
        <p class="focus-outcome"></p></div>''', 'html.parser').div
    grid.append(overlay)
    return section


old = soup.select_one('.controller-galleries')
previous_extra = soup.select_one('#controller-additional')
if previous_extra:
    previous_extra.decompose()
main = tag('div', **{'class': 'controller-galleries'})
for controller, label in [('optimized', 'MPC w/ optimization (ours)'), ('baseline', 'MPC (naive)')]:
    main.append(gallery(controller, label, 'primary'))
old.replace_with(main)
caption = main.find_next_sibling('p', class_='figure-caption')
if all(row.get('body') in ['g1','spot_arm'] for row in rows):
    assert len(rows)==4 and {(r['controller'],r['body']) for r in rows}=={
        (c,b) for c in ['optimized','baseline'] for b in ['g1','spot_arm']}
    assert all(row['scene'] and row['group']=='primary' for row in rows)
    main['class']='controller-galleries pushing-gallery'
    caption.string=('Object pushing with G1 and Spot + arm. Each pair shows the same body and object task. '
                    'Hover or select a video to enlarge it, then choose Play in 3D. '
                    'These are individual physical recordings of the complete controllers, not an isolated optimization ablation.')
    if any(row.get('costAblation') for row in rows):
        caption.string+=' The Spot + arm naive tile shows a labeled cost ablation. Its original recording remains linked.'
    elif any(row.get('variant') for row in rows):
        caption.string+=' The Spot + arm naive tile shows the labeled command-setting variant. Its original recording remains linked.'
else:
    caption.string = ('Hover or select a recorded task to enlarge its video, then choose Play in 3D. '
                      'Each result is one physical run. Failed attempts are labeled. '
                      'Empty tiles indicate missing recordings.')
if any(row['group']=='additional' for row in rows):
    extra = tag('section', id='controller-additional')
    extra.append(tag('h4', 'CLEAR scene'))
    pair = tag('div', **{'class': 'controller-galleries additional-galleries'})
    for controller, label in [('optimized', 'MPC w/ optimization (ours)'), ('baseline', 'MPC (naive)')]:
        pair.append(gallery(controller, label, 'additional'))
    extra.append(pair)
    caption.insert_after(extra)
(root/'index.html').write_text(str(soup).rstrip()+'\n')
print('Built controller galleries:', len(rows), 'recorded comparisons')
