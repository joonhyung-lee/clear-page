"""Replace the duplicate pushing gallery with a second body/EEF comparison row."""
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def apply(s):
    g1 = s.select_one('#mpc-process')
    g1['data-replay-body'] = 'g1'
    if not g1.select_one('.replay-body-title'):
        heading = s.new_tag('h4', attrs={'class': 'replay-body-title'})
        heading.string = 'G1'
        g1.insert(0, heading)
    summary = s.select_one('.controller-summary')
    if summary:
        s.select_one('.execution-pair').insert_before(summary.extract())
    if not s.select_one('#spot-process'):
        panel = BeautifulSoup('''<section id="spot-process" data-replay-body="spot" class="spot-process">
<h4 class="replay-body-title">Spot + arm</h4>
<div class="spot-process-controls"><div role="group" aria-label="Spot EEF view"><button type="button" data-spot-view="2d" aria-pressed="false">2D View</button><button type="button" data-spot-view="3d" aria-pressed="true">3D View</button></div><button type="button" data-spot-play>Play</button><button type="button" data-spot-replay>Replay</button><input type="range" min="0" max="1" step="0.0001" value="0" aria-label="Spot replay time"><output data-spot-time>0.0 s</output><span>2× replay</span></div>
<p class="spot-loading" role="status">Recorded trajectories load when nearby.</p>
<div class="execution-process-grid" role="region" tabindex="0" aria-label="Spot robot and end effector comparison"></div>
<p class="spot-replay-caption">Recorded EEF motion and object paths share the video clock. Each recording stops at its own endpoint.</p></section>''', 'html.parser').section
        for key, scene, label in [('optimized', 'mpc-spot-optimized', 'MPC w/ optimization (ours)'), ('baseline', 'mpc-spot-native', 'MPC (naive)')]:
            group = BeautifulSoup(f'''<section class="execution-controller" aria-labelledby="spot-heading-{key}"><h5 id="spot-heading-{key}">{label}</h5><div class="execution-controller-panels mpc-process-pair"><figure class="execution-record" aria-label="Spot robot replay"><div class="viewer execution-body-viewer" data-scene="{scene}" data-title="Spot + arm · {label}" data-ego="true" data-generation="true" data-external-timeline="true" data-execution-clock="{key}" data-clock-group="spot"><video class="preview-video" muted playsinline preload="none" poster="assets/media/{scene}.png"><source src="assets/media/{scene}.mp4" type="video/mp4"></video><div class="ego-inset"><span>Ego RGB</span><video muted playsinline preload="none" poster="assets/media/{scene}-ego.png" src="assets/media/{scene}-ego.mp4"></video></div><button class="launch" type="button">Inspect in 3D</button><output class="execution-clock-note"></output></div></figure><figure data-spot-process="{key}" aria-label="Spot end effector trajectory"><canvas width="560" height="420" tabindex="0" aria-label="Measured gripper trajectory in XYZ coordinates"></canvas><p class="mpc-recording-status">Recorded EEF motion</p></figure></div></section>''', 'html.parser').section
            panel.select_one('.execution-process-grid').append(group)
        s.select_one('.execution-pair').insert_after(panel)
    spot = s.select_one('#spot-process')
    if not spot.select_one('.spot-path-legend'):
        legend = BeautifulSoup('<div class="spot-path-legend"><span><i class="eef"></i>EEF motion</span><span><i class="object"></i>Object motion</span><span><i class="target"></i>Object target</span></div>', 'html.parser').div
        spot.select_one('.spot-process-controls').insert_after(legend)
    # These four videos are now presented once, by body, rather than twice by controller.
    for node in s.select('#method-execution .controller-details, #method-execution .pushing-gallery, #method-execution .pushing-motion-legend'):
        node.decompose()
    if not s.select_one('script[src^="assets/spot-eef.js"]'):
        s.head.append(s.new_tag('script', attrs={'src': 'assets/spot-eef.js', 'defer': ''}))
    from tidy_replay_headers import apply as tidy_headers
    return tidy_headers(s)


if __name__ == '__main__':
    path = ROOT/'index.html'
    path.write_text(str(apply(BeautifulSoup(path.read_text(), 'html.parser'))).rstrip()+'\n')
