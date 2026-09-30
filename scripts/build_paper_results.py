"""Publish the anonymous manuscript's Tables I–IV alongside individual replays."""
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
soup=BeautifulSoup((ROOT/'index.html').read_text(),'html.parser')
tables = [
 ('grid','I',6,['Method','Task S/R ↑','Min. S/R ↑','Coverage@8 ↑','Invalid@8 ↓'],'''
Autoregressive|92.31 ± 0.64|92.31 ± 0.64|82.20 ± 0.21|7.49 ± 0.98
Gumbel–Sinkhorn|91.81 ± 0.96|79.77 ± 5.66|72.20 ± 4.40|9.38 ± 1.03
PolyNet|89.49 ± 2.74|89.49 ± 2.74|85.95 ± 0.43|16.88 ± 5.18
CLEAR-RO|34.12 ± 2.19|34.12 ± 2.19|61.93 ± 0.92|64.33 ± 0.63
CLEAR-HO|61.76 ± 1.71|61.67 ± 1.61|59.51 ± 0.18|39.21 ± 0.43
CLEAR|96.16 ± 0.67|96.02 ± 0.55|88.11 ± 0.32|6.43 ± 0.59
''','Mean ± sample SD (%) over five training seeds on 432 test scenes. Coverage@8 and Invalid@8 use the first eight proposals per scene.',
 'Which objects must move, and in what order?',
 'CLEAR achieves the highest mean task and minimum-interaction success, with the lowest mean invalid proposal rate among these methods.'),
 ('manipulation','II',6,['Method','Task S/R ↑','Valid S/R ↑','Invalid E/R ↓'],'''
Classical Search|83.80 ± 2.17|83.80 ± 2.17|0.83 ± 0.72
BC|90.25 ± 1.78|87.50 ± 2.59|3.33 ± 2.72
BC-Grounding|87.42 ± 1.89|87.42 ± 1.89|0.67 ± 1.09
CLEAR w/o affordance|89.67 ± 3.50|85.33 ± 5.71|7.75 ± 5.29
CLEAR w/o rank mask|91.42 ± 1.97|90.33 ± 2.29|3.08 ± 3.20
CLEAR|92.17 ± 1.04|91.92 ± 1.40|1.28 ± 2.44
''','Mean ± SD (%) over five training seeds for learned methods and three execution seeds for Classical Search.',
 'Are interaction preconditions satisfied?',
 'CLEAR has the highest mean valid success. Classical Search and BC-Grounding have lower invalid episode rates.'),
 ('maze','III',7,['Method','Standard G1 S/R','Standard Spot S/R','Standard Spot+Arm S/R','Standard Husky P/A','High-Mass G1 S/R','High-Mass Spot S/R','High-Mass Spot+Arm S/R','High-Mass Husky P/A'],'''
NAMO-LLM|64.4|53.3|13.3|55.6|26.7|26.7|0.0|20.0
NAMO w/o LLM|62.2|44.4|13.3|46.7|40.0|20.0|0.0|13.3
CDGS|42.2|60.0|4.4|73.3|0.0|36.7|6.7|83.3
CLEAR-Specialists|97.8|93.3|93.3|95.6|73.3|70.0|93.3|100.0
CLEAR-Robot-ID|93.3|82.2|88.9|82.2|93.3|56.7|93.3|86.7
CLEAR + GET|97.8|86.7|75.6|86.7|93.3|60.0|86.7|90.0
CLEAR-No-Affordance|91.1|75.6|60.0|77.8|76.7|50.0|93.3|80.0
CLEAR-No-Embodiment|55.6|53.3|82.2|33.3|6.7|30.0|83.3|10.0
CLEAR|91.1|91.1|95.6|93.3|93.3|66.7|96.7|100.0
''','Means (%) over three training seeds for learned methods and three execution seeds for NAMO variants. Each method and body has 45 Standard and 30 High-Mass trials. Husky uses planning accuracy (P/A), other bodies use task success (S/R). Higher is better for each column. No high-level replanning.',
 'How does the robot body change the plan?',
 'The shared planner improves over the adapted external planners in every listed setting. Specialists and alternative encoders remain stronger in some comparisons.'),
 ('horizon','IV',7,['Method','Nominal S/R ↑','Placement S/R ↑','Access S/R ↑'],'''
CLEAR-No-Replanning|83.3 ± 4.8|81.9 ± 0.0|50.0 ± 14.4
CLEAR|88.9 ± 4.8|87.2 ± 14.4|91.7 ± 8.3
''','Mean ± SD success rates (%) for G1 on 12 MuJoCo scenes with three execution seeds. Aggregate trials are separate from the additional qualitative replays above.',
 'Can the plan recover after the scene changes?',
 'Replanning has its largest measured benefit when disturbances change access to later interactions, from 50.0% to 91.7% mean success.')
]
for key, number, page, headers, data, protocol, question, takeaway in tables:
    section=soup.find(id='experiment-'+key)
    for old in section.select('.paper-results,.result-takeaway,.all-methods-toggle'):
        old.decompose()
    section.select_one('.experiment-claim').string=question
    panel=soup.new_tag('div',attrs={'class':'paper-results'})
    h=soup.new_tag('h4');h.string='Quantitative results';panel.append(h)
    note=soup.new_tag('p');note.string='Paper aggregate · Table '+number+' · '+protocol;panel.append(note)
    scroll=soup.new_tag('div',attrs={'class':'result-table-scroll','tabindex':'0','role':'region','aria-label':'Table '+number+' results'})
    table=soup.new_tag('table');head=soup.new_tag('thead');row=soup.new_tag('tr')
    for label in headers:
        cell=soup.new_tag('th',scope='col');cell.string=label;row.append(cell)
    head.append(row);table.append(head);body=soup.new_tag('tbody')
    lines=[line.split('|') for line in data.strip().splitlines()]
    for index, fields in enumerate(lines):
        assert len(fields)==len(headers)
        row=soup.new_tag('tr')
        if index>=2 and fields[0]!='CLEAR':row['class']='secondary-method'
        for i,value in enumerate(fields):
            cell=soup.new_tag('th',scope='row') if i==0 else soup.new_tag('td');cell.string=value;row.append(cell)
        body.append(row)
    table.append(body);scroll.append(table);panel.append(scroll)
    source=soup.new_tag('a',href=f'assets/clear-paper.pdf#page={page}',target='_blank',rel='noopener');source.string='View Table '+number+' in the paper';panel.append(source)
    section.append(panel)
    takeaway_node=soup.new_tag('p',attrs={'class':'result-takeaway'});takeaway_node.string=takeaway;section.append(takeaway_node)
    details=section.select_one('.result-protocol-details')
    if not details:
        details=soup.new_tag('details',attrs={'class':'research-details result-protocol-details'})
        summary=soup.new_tag('summary');summary.string='Scene and protocol';details.append(summary)
    else:
        details.extract()
    replays=section.find(id=f'experiment-{key}-replays')
    if replays:
        replays.select_one('h4').string='Recorded comparison'
        for child in list(replays.find_all(recursive=False)):
            if child.name=='label' or (child.name=='p' and 'result-replay-label' not in child.get('class',[])):
                details.append(child.extract())
    section.append(details)
    for label in section.select('.result-replay-label'):label.decompose()
    for matrix in section.select('.experiment-matrix'):
        cards=matrix.find_all('article',recursive=False)
        preferred=[c for c in cards if 'CLEAR (ours)' in c.get_text()]
        preferred += [c for c in cards if c not in preferred][:max(0,3-len(preferred))]
        for card in cards:
            classes=[c for c in card.get('class',[]) if c!='secondary-method']
            if card not in preferred:classes.append('secondary-method')
            card['class']=classes
            if not card.select_one('.record-scope'):
                scope=soup.new_tag('p',attrs={'class':'record-scope'})
                text=card.get_text(' ',strip=True)
                scope.string=('Qualitative replay · Not part of aggregate evaluation' if key=='horizon'
                    else 'No valid plan · No execution recorded' if 'Static scene only' in text
                    else 'Recorded simulation · Single episode')
                card.append(scope)
        if not section.select_one('.result-replay-label'):
            label=soup.new_tag('p',attrs={'class':'result-replay-label'})
            label.string='Qualitative replay · Not part of aggregate evaluation' if key=='horizon' else 'Recorded simulation · Individual episodes'
            matrix.insert_before(label)
    button=soup.new_tag('button',type='button',attrs={'class':'all-methods-toggle','aria-expanded':'false'})
    button.string='All methods';section.select_one('.experiment-claim').insert_after(button)
(ROOT/'index.html').write_text(str(soup).rstrip()+'\n')
