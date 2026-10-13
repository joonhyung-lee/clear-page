"""Introduce the planning task before the pipeline's formal notation."""
from pathlib import Path
from bs4 import BeautifulSoup

LEAD = ('CLEAR plans how a robot can reach its goal by moving objects in the scene. '
        'It decides which objects to move, in what order, and how to move them, '
        'taking the robot’s capabilities and the effects of earlier interactions into account.')
from method_stage_content import markup

NOTATION = markup()

def apply(soup):
    overview = soup.select_one('#clear-overview')
    intro=overview.select_one('.overview-intro');intro.clear()
    html=LEAD.replace('which objects to move, in what order, and how to move them','<mark>which objects to move, in what order, and how to move them</mark>')
    for child in list(BeautifulSoup(html,'html.parser').contents):intro.append(child)
    old = overview.select_one('.overview-notation')
    if old:
        old.decompose()
    overview.select_one('.overview-flow').insert_after(BeautifulSoup(NOTATION, 'html.parser').div)

if __name__ == '__main__':
    path = Path(__file__).resolve().parents[1] / 'index.html'
    soup = BeautifulSoup(path.read_text(), 'html.parser')
    apply(soup)
    path.write_text(str(soup).rstrip() + '\n')
