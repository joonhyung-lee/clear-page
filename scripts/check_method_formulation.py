"""Check paper notation, component links and the shared flow-time schematic.

This check runs without a web server. Browser layout checks remain separate.
"""
import json
import subprocess
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
soup = BeautifulSoup((ROOT / 'index.html').read_text(), 'html.parser')
components = [
    ('a', 'grounding', 'method-grounding', 'Embodiment-Aware Scene Grounding'),
    ('b', 'ordering', 'method-order', 'Latent Interaction Ordering'),
    ('c', 'generation', 'method-flow', 'Rank-Causal Generation'),
    ('d', 'execution', 'method-execution', 'Execution and Replanning'),
]
for letter, stage, target, title in components:
    expected = f'({letter}) {title}'
    assert soup.select_one('#'+target+'>h3').get_text() == expected
    assert soup.select_one(f'[data-overview-stage="{stage}"]')['aria-label'] == expected
    assert soup.select_one(f'#method .chapter-links a[href="#{target}"]').get_text().startswith(f'({letter}) ')
for target, rule in [('method-order', 'ordering-rule'), ('method-flow', 'generation-rule')]:
    section = soup.select_one('#'+target)
    children = list(section.children)
    assert children.index(section.select_one('figure')) < children.index(section.select_one('#'+rule)) < children.index(section.select_one('.method-lead'))
    assert len(section.select(':scope > .method-explanation')) == 1
    assert section.select_one('.method-example')
order = soup.select_one('#ordering-rule [data-tex]')['data-tex']
assert all(term in order for term in ['Bernoulli', 'q_i', '\\mathcal I', '\\mu_i', '\\sigma_i^2', 'argsort'])
flow = soup.select_one('#generation-rule [data-tex]')['data-tex']
assert all(term in flow for term in ['\\mathbf Y_t', '\\mathbf H', '\\boldsymbol\\rho', '\\Delta t'])
assert '\\dot{\\mathbf{x}}' not in flow
assert 'not execution time' in soup.select_one('#method-flow>.method-lead').get_text()
assert 'Context tokens cannot read generated rows' in soup.select_one('#method-flow .method-explanation').get_text()
assert 'Maze Navigation comparisons omit high-level replanning' in soup.select_one('#method-execution>.method-small-copy').get_text()
assert soup.select_one('.planning-scope') is None
formulas = [node['data-tex'] for node in soup.select('[data-tex]')]
javascript = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const katex=require('./assets/katex/katex.min.js');
const formulas=JSON.parse(fs.readFileSync(0,'utf8'));
for(const formula of formulas)katex.renderToString(formula,{throwOnError:true,strict:'error'});
const source=fs.readFileSync('assets/method-illustration.js','utf8');
const prefix=source.slice(source.indexOf(' const objects='),source.indexOf(' const controls='));
const api=vm.runInNewContext(prefix+';({scene,objects});',{reduced:{matches:true}});
function paths(t){const svg=api.scene('2d','flow',t);return [...svg.matchAll(/class="generated-path" points="([^"]+)"/g)].map(m=>m[1].split(' ').map(p=>p.split(',').map(Number)));}
const start=paths(0),end=paths(1);assert.equal(start.length,2);
for(const t of [.25,.5,.75]){
 const current=paths(t);
 for(let object=0;object<2;object++)for(let point=0;point<4;point++)for(let axis=0;axis<2;axis++){
  const expected=(1-t)*start[object][point][axis]+t*end[object][point][axis];
  assert(Math.abs(current[object][point][axis]-expected)<1e-8,'Both selected rows must evolve over the same flow interval');
 }
}
const output=api.scene('2d','ordering',1);
for(const label of ['o₁','o₂','o₃'])assert(output.includes(label));
assert(!output.includes('OBJ 0'));
assert.equal((output.match(/class="selection-ring"/g)||[]).length,2);
console.log('PASS '+formulas.length+' rendered equations, shared flow time for both selected rows, paper object labels');
'''
subprocess.run(['node', '-e', javascript], cwd=ROOT, input=json.dumps(formulas), text=True, check=True)
print('PASS manuscript component names, navigation, selection and generation notation, concrete examples and protocol scope')
