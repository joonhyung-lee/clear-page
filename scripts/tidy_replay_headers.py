"""Label each robot/EEF pair directly, with one time readout per body row."""


def apply(s):
    execution = s.select_one('#method-execution')
    for headings in execution.select('.replay-comparison-headings'):
        headings.decompose()
    for root_id, controls_selector in [('mpc-process', '.mpc-process-controls'), ('spot-process', '.spot-process-controls')]:
        root = s.select_one('#'+root_id)
        controls = root.select_one(controls_selector)
        controls['class'] = list(dict.fromkeys(controls.get('class', [])+['replay-toolbar']))
        title = root.select_one('.replay-body-title')
        controls.insert(0, title.extract())
        for group, key, label in zip(root.select('.execution-controller'), ['ours', 'naive'], ['MPC w/ optimization (ours)', 'MPC (naive)']):
            heading = root_id+'-'+key+'-heading'
            group['aria-labelledby'] = heading
            group['data-controller-pair'] = key
            title_node = group.select_one(':scope > h5')
            if not title_node:
                title_node = s.new_tag('h5')
                group.insert(0, title_node)
            title_node['id'] = heading
            title_node.string = label
        for node in root.select('.execution-clock-note'):
            node.decompose()
        for node in root.select('.mpc-recording-status'):
            node.clear()
        for button in root.select('[data-mpc-view], [data-spot-view]'):
            mode = button.get('data-mpc-view', button.get('data-spot-view'))
            button.string = mode.upper()
            button['aria-label'] = mode.upper()+' trajectory view'
        # Keep the same control order for both bodies.
        if root_id == 'mpc-process':
            if not root.select_one('#mpc-process-replay'):
                replay = s.new_tag('button', attrs={'id': 'mpc-process-replay', 'type': 'button'})
                replay.string = 'Replay'
                root.select_one('#mpc-process-play').insert_after(replay)
            order = ['.replay-body-title', '#mpc-process-play', '#mpc-process-replay', '.mpc-timeline', '#mpc-process-counter', '.mpc-playback-speed', '.mpc-view-controls', '#mpc-robot-context', '.mpc-full-control']
            root.select_one('.mpc-playback-speed').string = '2×'
            context = root.select_one('#mpc-robot-context')
            context.string = 'Skeleton'
            context['title'] = 'Show the recorded robot skeleton with the palm trajectories'
            pin = root.select_one('.mpc-time-pin')
            pin.string = ''
            pin['aria-label'] = 'Seek to first interaction completion at 14 seconds'
            label = root.select_one('.mpc-full-control')
            for text in list(label.find_all(string=True, recursive=False)):
                text.replace_with(' Full 40 s')
        else:
            order = ['.replay-body-title', '[data-spot-play]', '[data-spot-replay]', 'input', '[data-spot-time]', ':scope > span', '[role="group"]']
            controls.select_one(':scope > span').string = '2×'
        for selector in order:
            node = controls.select_one(selector)
            if node:
                controls.append(node.extract())
    for note in execution.select('.mpc-phase-note, .spot-replay-caption'):
        note.decompose()
    for notes in execution.select('.replay-comparison-notes'):
        notes.decompose()
    legend = s.select_one('.spot-path-legend')
    if legend:
        s.select_one('#spot-process .execution-process-grid').insert_after(legend.extract())
    return s
