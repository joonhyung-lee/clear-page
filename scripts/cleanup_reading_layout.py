"""Apply the compact reading layout to the page and its generated form."""
from pathlib import Path
from bs4 import BeautifulSoup


def apply(s):
    for n in s.select('.overview-input-links, .experiment-supervision, #experiments > .chapter-links, #mpc-process > h4, #mpc-process > .method-small-copy'):
        n.decompose()
    note = s.select_one('#method-execution > .method-small-copy')
    if note:
        protocol = s.select_one('#experiment-maze .result-protocol-details')
        if protocol and not protocol.select_one('[data-validation-scope]'):
            note['data-validation-scope'] = ''
            protocol.append(note.extract())
    for details in s.select('#method-execution > details'):
        summary = details.select_one(':scope > summary')
        if summary and summary.get_text(strip=True) == 'Controller details':
            summary.decompose()
            details.name = 'div'
            details.attrs = {'class': 'controller-details'}
    for n in s.find_all(string=True):
        if n.parent.name not in ['script', 'style'] and 'native sumo' in str(n).lower():
            import re
            n.replace_with(re.sub('native SUMO', 'MPC (naive)', str(n), flags=re.I))
    for node in s.select('[data-protocol-label]'):
        node.attrs.pop('data-protocol-label', None)

    experiments = s.select_one('#experiments')
    if not s.select_one('.experiment-scenes'):
        figure = s.new_tag('div', attrs={'class': 'experiment-scenes', 'aria-label': 'Experimental environments'})
        scenes = [
            ('grid', '2D Grid', 'grid-chain-clear', 'Select and relocate obstacles to connect start and goal.'),
            ('manipulation', 'Ordered Manipulation', 'manipulation-clear', 'Order interactions so later objects remain accessible.'),
            ('maze', 'Maze Navigation', 'maze-e03-highmass-g1-clear', 'Plan around terrain and movable objects for each body.'),
            ('horizon', 'Long Horizon Planning', 'horizon-A-contrast-heavy02-clear', 'Update the plan when object placement or access changes.'),
        ]
        for i, (target, title, scene, caption) in enumerate(scenes):
            fragment = BeautifulSoup(f'<figure><a href="#experiment-{target}"><img src="assets/media/{scene}.png" alt="{title} environment" loading="lazy" width="700" height="540"><figcaption><strong>({chr(97+i)}) {title}</strong><span>{caption}</span></figcaption></a></figure>', 'html.parser')
            figure.append(fragment.figure)
        experiments.select_one('.section-heading').insert_after(figure)
    horizon = s.select_one('#experiment-horizon-replays')
    if horizon and not horizon.select_one('.horizon-scenes'):
        row = s.new_tag('div', attrs={'class': 'horizon-scenes', 'role': 'region', 'aria-label': 'Scene A and Scene B comparisons', 'tabindex': '0'})
        for label in list(horizon.select(':scope > .comparison-label')):
            group = s.new_tag('section', attrs={'class': 'horizon-scene'})
            matrix = label.find_next_sibling('div', class_='experiment-matrix')
            group.append(label.extract())
            group.append(matrix.extract())
            row.append(group)
        horizon.append(row)
    for viewer in s.select('#mpc-process [data-execution-clock="baseline"]'):
        viewer['data-contact-side'] = 'false'
    for caption in s.select('.execution-record > .record-scope'):
        caption.decompose()
    caption = s.select_one('.pushing-gallery > .figure-caption')
    if caption and not s.select_one('.pushing-gallery .original-recording'):
        caption.string = 'Recorded pushing with G1 and Spot + arm. Hover to enlarge or inspect in 3D. Complete controllers are compared, with their own reset and stopping criteria.'
    # Keep one short explanation of each failure. Playback starts at the reset.
    failure = s.select_one('[data-failure-example="execution"]')
    failure.select_one('video')['poster'] = 'assets/media/mpc-baseline-contact.png'
    failure.select_one('.failure-event').string = 'Approaching the object'
    failure.select_one('p').string = 'Contact is lost at 14.14 s. The box settles 1.33 m short of the goal while the robot continues walking.'
    failure.select_one('.failure-status').decompose() if failure.select_one('.failure-status') else None
    for kind in ['planning', 'transfer']:
        article = s.select_one(f'[data-failure-example="{kind}"]')
        if kind == 'planning':
            img = article.select_one('.failure-visual img')
            if img:
                img.replace_with(s.new_tag('canvas', attrs={'data-planning-failure': '', 'aria-label': 'Recorded planning candidates and rejection decisions'}))
            article.select_one('p').string = 'Archived proposals and recorded rejection decisions. No physical execution.'
        else:
            article.select_one('p').string = 'Saved flow predictions for three objects. Red paths fail geometric clearance and are not executed.'
        badge = article.select_one('.failure-status')
        if badge:
            badge.decompose()
        if not article.select_one('.failure-controls'):
            label = 'Flow time' if kind == 'transfer' else 'Planning candidate sequence'
            controls = BeautifulSoup(f'<div class="failure-controls"><button type="button" data-failure-play>Play</button><button type="button" data-failure-replay>Replay</button><input type="range" min="0" max="1" step="0.001" value="0" aria-label="{label}"><output>0</output></div><div class="failure-stage" role="status"></div>', 'html.parser')
            description = article.select_one(':scope > p')
            for node in list(controls.contents):
                description.insert_before(node.extract())
    for node in s.select('.native-protocol-label, .controller-variant'):
        if node.get_text(strip=True).lower() in ('native sumo', 'mpc (naive)'):
            node.decompose()
    from build_body_replays import apply as apply_body_replays
    return apply_body_replays(s)


if __name__ == '__main__':
    path = Path(__file__).resolve().parents[1] / 'index.html'
    path.write_text(str(apply(BeautifulSoup(path.read_text(), 'html.parser'))).rstrip() + '\n')
