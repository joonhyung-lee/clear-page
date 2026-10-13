"""Place the joint objective beside its component curves, above sample explorers."""
from pathlib import Path
from bs4 import BeautifulSoup
from training_objective_content import ROLES, CAPTIONS


def apply(s):
    pair = s.select_one('#learning .learning-pair')
    if not pair:
        return s
    planner = s.select_one('#learning-planner')
    samples = s.select_one('#learning-data')
    pair.insert(0, planner.extract())
    for detail in list(planner.select(':scope > details')):
        title = detail.select_one('summary')
        if title and title.get_text(strip=True) in ('Flow matching and causal conditioning', 'Affordance supervision'):
            detail.decompose()
    for heading in planner.select('h4'):
        if heading.get_text(strip=True) == 'The full training objective':
            heading.decompose()
    losses = s.select_one('#training-losses')
    losses.attrs.pop('data-loss-source', None)
    losses.select_one('#loss-loss figcaption p').string = '100,000 training steps'
    copy = losses.select_one('.training-objective-copy')
    if not copy:
        copy = s.new_tag('div', attrs={'class': 'training-objective-copy'})
        for selector in (':scope > .method-small-copy', ':scope > .paper-equation-row', ':scope > .loss-scope'):
            node = losses.select_one(selector)
            if node:
                copy.append(node.extract())
        losses.insert(0, copy)
    equation = losses.select_one('[data-objective-annotations]')
    equation['data-tex'] = r'\mathcal{L}(\theta)=\mathcal{L}_{\mathrm{order}}+\lambda_{\mathrm{flow}}\mathcal{L}_{\mathrm{flow}}+\lambda_{\mathrm{aff}}\mathcal{L}_{\mathrm{aff}}+\lambda_{\mathrm{avail}}\mathcal{L}_{\mathrm{avail}}'
    content = losses.select_one('.loss-content')
    scope = losses.select_one('.loss-scope:not(.loss-band-note)')
    content.insert(0, scope.extract())
    for old in list(losses.select('.loss-role-guide')):
        old.decompose()
    scope.insert_after(BeautifulSoup(ROLES, 'html.parser'))
    if not losses.select_one('[data-loss-composition]'):
        composition = s.new_tag('div', attrs={'class': 'loss-composition', 'data-loss-composition': '', 'aria-label': 'Weighted contributions to the full objective'})
        losses.select_one('#loss-loss').insert_after(composition)
    for key, text in CAPTIONS.items():
        losses.select_one(f'[data-loss="{key}"] figcaption p').string = text
    progress = s.select_one('#planner-progress')
    if progress:
        progress.decompose()
    for note in list(losses.select('.loss-band-note')):
        note.decompose()
    grid = losses.select_one('.loss-chart-grid')
    grid['aria-label'] = 'Five component training losses'
    grid.attrs.pop('tabindex', None)
    # Pair the total and its formula with the component curves.
    split = losses.select_one('.training-objective-split')
    if not split:
        split = s.new_tag('div', attrs={'class': 'training-objective-split'})
        losses.insert(0, split)
    main = split.select_one('.training-objective-main')
    if not main:
        main = s.new_tag('div', attrs={'class': 'training-objective-main'})
        split.append(main)
    for node in (losses.select_one('#loss-loss'), copy, losses.select_one('[data-loss-composition]'), scope):
        main.append(node.extract())
    for overview in losses.select('.training-objective-overview'):
        overview.decompose()
    split.append(content.extract())
    samples.select_one(':scope > p').string = 'Training samples for scene grounding and interaction planning.'
    for ident, text in (
        ('grounding-samples', '(a) Grounding · Feasibility samples'),
        ('ordering-samples', '(b–c) Ordering and generation · Reference plans'),
    ):
        panel = s.select_one('#' + ident)
        heading = panel.select_one('.training-sample-heading')
        if not heading:
            heading = s.new_tag('h4', attrs={'class': 'training-sample-heading'})
            panel.insert(0, heading)
        heading.string = text
    # Keep in-page links in the same order as the content.
    nav = s.select_one('#learning > .chapter-links')
    link = nav.select_one('a[href="#learning-planner"]')
    link.string = 'Training objective'
    nav.insert(0, link.extract())
    rail = s.select_one('#section-rail')
    if rail:
        anchor = rail.select_one('a[href="#learning"]')
        for target, label in (('learning-planner', '(a) Objective'), ('learning-data', '(b) Samples'), ('controller-pretraining', '(c) Policy training')):
            old = rail.select_one(f'a[href="#{target}"]')
            if old:
                old.decompose()
            link = s.new_tag('a', href='#' + target, attrs={'class': 'rail-subsection'})
            link.string = label
            anchor.insert_after(link)
            anchor = link
    return s


if __name__ == '__main__':
    page = Path(__file__).resolve().parents[1] / 'index.html'
    page.write_text(str(apply(BeautifulSoup(page.read_text(), 'html.parser'))).rstrip() + '\n')
