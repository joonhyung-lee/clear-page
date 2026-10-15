"""Local page preview backed by the current training log; published assets stay intact."""
import argparse
import base64
import gzip
import io
import json
import math
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from serve import Handler


def training_payload(run, max_step=None):
    config = json.loads((run / 'protocol.json').read_text())['config']
    weight = config['model']['availability_weight']
    samples = []
    # A running writer may leave an incomplete final line while this snapshot is read.
    raw = (run / 'training.jsonl').read_bytes()
    for line in raw[:raw.rfind(b'\n') + 1].splitlines():
        row = json.loads(line)
        if 'loss' not in row:
            continue
        if max_step is not None and row['step'] > max_step:
            break
        sample = {k: row[k] for k in (
            'step', 'loss', 'selection', 'order', 'kl', 'flow', 'affordance', 'availability')}
        total = (row['selection'] + row['order'] + .001 * row['kl']
                 + row['flow'] + row['affordance'] + weight * row['availability'])
        if (not all(math.isfinite(v) for v in sample.values())
                or not math.isclose(total, row['loss'], abs_tol=3e-6, rel_tol=3e-6)
                or (samples and sample['step'] <= samples[-1]['step'])):
            raise ValueError('Inconsistent training log')
        samples.append(sample)
    if not samples:
        raise ValueError('No training metrics yet')
    return dict(samples=samples, maxStep=samples[-1]['step'], window=21,
                weights=dict(kl=.001, flow=1, affordance=1, availability=weight),
                complete=(run / 'complete.json').exists(), targetStep=config['steps'])


class TrainingHandler(Handler):
    def send_head(self):
        path = urlsplit(self.path).path
        if path not in ('/assets/training-loss-data.js', '/assets/training-loss-data.packed.js'):
            return super().send_head()
        self.range_remaining = None
        try:
            payload = training_payload(self.server.training_run, self.server.max_step)
        except (OSError, ValueError, KeyError):
            self.send_error(503, 'Training metrics are temporarily unavailable')
            return None
        data = json.dumps(payload, separators=(',', ':'), allow_nan=False)
        if path.endswith('.packed.js'):
            packed = base64.b64encode(gzip.compress(data.encode(), mtime=0)).decode()
            body = (
                'window.CLEAR_DATA_READY=window.CLEAR_DATA_READY||{};\n'
                'window.CLEAR_DATA_READY["assets/training-loss-data.packed.js"]=(async()=>{\n'
                f'const bytes=Uint8Array.from(atob("{packed}"),c=>c.charCodeAt(0));\n'
                "const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));\n"
                'window.CLEAR_TRAINING_LOSSES=JSON.parse(await new Response(stream).text());\n'
                '})();\n'
            ).encode()
        else:
            body = ('window.CLEAR_TRAINING_LOSSES=' + data + ';\n').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        return io.BytesIO(body)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8774)
    parser.add_argument('--max-step', type=int, help='Limit the preview to this training step')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), TrainingHandler)
    server.training_run = args.run.resolve()
    server.max_step = args.max_step
    print(f'Training preview: http://localhost:{args.port}/#training-objective', flush=True)
    server.serve_forever()
