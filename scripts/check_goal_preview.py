"""Run the goal's browser checks on a local preview and keep a private report.

Run in a terminal where localhost binding and Chromium are permitted. If this
runner starts a server, it stops that server when the checks finish. An existing
server is retained and must serve the current worktree's exact index.html.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ['check_learning_tree.py', 'check_teaser_method.py', 'check_teaser_replay.py', 'check_pushing_gallery.py', 'check_controller_pretraining.py', 'check_spot_curriculum.py', 'check_training_layout.py', 'check_learning_replay.py',
          'check_training_losses.py', 'check_policy_evaluation.py', 'check_g1_scratch.py', 'check_flow_learning.py',
          'check_grounding_inputs.py', 'check_learning_explorers.py',
          'check_interactive_mpc.py']
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', choices=CHECKS, action='append',
                    help='Run only this check. Repeat to select multiple checks.')
args = parser.parse_args()
selected = list(dict.fromkeys(args.check or CHECKS))
report_dir = Path(tempfile.mkdtemp(prefix='clear-preview-check-'))
results = []
server = None


def page_bytes():
    with urlopen('http://localhost:8765/', timeout=3) as response:
        return response.read()


try:
    try:
        served = page_bytes()
    except OSError:
        log = (report_dir/'server.log').open('w')
        server = subprocess.Popen([sys.executable,str(ROOT/'scripts/serve.py'),'--port','8765'],
                                  cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        for _ in range(50):
            if server.poll() is not None:
                raise RuntimeError('Local preview could not start: '+(report_dir/'server.log').read_text())
            try:
                served = page_bytes()
                break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError('Local preview did not become available')
    assert served == (ROOT/'index.html').read_bytes(), 'Port 8765 is serving a different version of index.html'
    for name in selected:
        print('Checking',name,flush=True)
        with (report_dir/(name+'.log')).open('w') as check_log:
            with subprocess.Popen([sys.executable,'-u',str(ROOT/'scripts'/name)],cwd=ROOT,
                                  text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                  env={**os.environ, 'CLEAR_CHECK_REPORT_DIR':str(report_dir)}) as process:
                for line in process.stdout:
                    check_log.write(line);check_log.flush()
                    if line.startswith(('PROGRESS ', 'Browser diagnostics:', 'PASS ', 'FAIL ')):
                        print(' ',line.rstrip(),flush=True)
                code=process.wait()
        results.append(dict(check=name,passed=code==0,exitCode=code))
        print('PASS' if code==0 else 'FAIL',name,flush=True)
    report = dict(indexSHA256=hashlib.sha256(served).hexdigest(),results=results)
    (report_dir/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Report:',report_dir/'report.json',flush=True)
    raise SystemExit(0 if all(r['passed'] for r in results) else 1)
except Exception as error:
    (report_dir/'report.json').write_text(json.dumps(dict(
        status='blocked', reason=str(error), results=results),indent=2)+'\n')
    print('Preview checks could not run:',str(error).splitlines()[0],flush=True)
    print('Report:',report_dir/'report.json',flush=True)
    raise SystemExit(2) from None
finally:
    if server is not None and server.poll() is None:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
