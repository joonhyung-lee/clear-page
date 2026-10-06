"""Check the anonymous website, then optionally commit and push main.

Default is a read-only publication check. --push stages the reviewed working tree.
A large model archive stays local until an anonymous external URL is supplied.
"""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 100 * 1024 * 1024
LOCATIONS = ROOT / 'assets/code-download-locations.js'


def run(*args, capture=False, env=None, check=True):
    return subprocess.run(args, cwd=ROOT, env=env, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def owner():
    remote = run('git', 'remote', 'get-url', 'origin', capture=True).stdout.strip()
    match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:)([\w-]+)/([\w.-]+?)(?:\.git)?', remote)
    if not match:
        raise ValueError('Expected a GitHub origin without embedded credentials')
    return match[1]


def check_url(url, terms):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Use an HTTPS download URL without credentials or fragments')
    host = parsed.hostname.lower()
    if any(host == domain or host.endswith('.'+domain) for domain in
           ['github.com', 'githubusercontent.com', 'github.io']):
        raise ValueError('A direct personal GitHub download is unsuitable for anonymous publication')
    visible = unquote(url).lower()
    if any(term.lower() in visible for term in terms if len(term) > 3):
        raise ValueError('The download URL contains a private identifier')
    if parsed.query:
        raise ValueError('Use a stable public URL without signed or identifying query parameters')
    return url


def files_to_publish():
    result = run('git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard', capture=True)
    return sorted({ROOT / name for name in result.stdout.split('\0') if name and (ROOT / name).is_file()})


def check_payloads(paths):
    too_large = [str(p.relative_to(ROOT)) for p in paths if p.stat().st_size > LIMIT]
    if too_large:
        raise ValueError('Files exceed the Git limit: '+', '.join(too_large))
    excluded = ['assets/code-downloads/clear-pretrained.zip',
                'replanning/htx-demo-standalone.html', 'replanning/htx-demo-workload.html']
    included = {str(p.relative_to(ROOT)) for p in paths}
    if included.intersection(excluded):
        raise ValueError('A local-only archive or reference is still included')
    print(f'PASS publication scope: {len(paths)} files; no oversized Git payload', flush=True)


def check_anonymity(terms):
    command = [sys.executable, str(ROOT/'scripts/audit_anonymity.py')]
    for term in terms:
        command += ['--term', term]
    result = run(*command, capture=True, check=False)
    reviewed = json.loads((ROOT/'scripts/publish_reviewed_sources.json').read_text())
    failures = [line for line in result.stdout.splitlines() if line.startswith('FAIL ')]
    if not result.returncode:
        print(result.stdout.strip(), flush=True)
        return
    if result.returncode != 1 or not failures or result.stderr:
        raise ValueError('Anonymity audit did not complete: '+result.stderr[-800:])
    unexpected = []
    for line in failures:
        label, reason = line[5:].rsplit(': ', 1)
        entry = reviewed.get(label)
        if not entry or reason != 'private path or email' or not (ROOT/label).is_file():
            unexpected.append(line)
            continue
        actual = hashlib.sha256((ROOT/label).read_bytes()).hexdigest()
        if actual != entry['sha256']:
            unexpected.append(line+' (reviewed file changed)')
    if unexpected:
        raise ValueError('Anonymity audit needs review:\n'+'\n'.join(unexpected))
    print(f'PASS automated identifier/metadata checks with {len(failures)} hash-pinned, reviewed test/syntax exceptions', flush=True)


def check_archives():
    metadata = json.loads((ROOT/'assets/code-archives.js').read_text().split('=', 1)[1].strip().removesuffix(';'))
    for key, entry in metadata.items():
        path = (ROOT/'code'/entry['url']).resolve()
        if key == 'checkpoints' and not path.exists():
            continue
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != entry['sha256']:
            raise ValueError('Archive differs from verified inventory: '+key)
    print('PASS archive checksums', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--push', action='store_true', help='Commit all reviewed changes and push main without forcing')
    parser.add_argument('--checkpoint-url', help='Public anonymous download URL, reviewed for owner/redirect disclosure')
    parser.add_argument('--term', action='append', default=[], help='Additional private identifier to check; never saved')
    args = parser.parse_args()
    account = owner()
    terms = [account, getpass.getuser(), *args.term]
    if args.push and os.statvfs(ROOT/'.git').f_flag & os.ST_RDONLY:
        raise ValueError('Git metadata is read-only in this session. Run this command in your normal terminal.')
    if args.checkpoint_url:
        url = check_url(args.checkpoint_url, terms)
        LOCATIONS.write_text('window.CLEAR_CODE_DOWNLOADS='+json.dumps({'checkpoints': url})+';\n')
    if args.push or args.checkpoint_url:
        run(sys.executable, 'scripts/build_asset_revisions.py')
        run(sys.executable, 'scripts/build_code_browser.py')
    locations = json.loads(LOCATIONS.read_text().split('window.CLEAR_CODE_DOWNLOADS=', 1)[1].strip().removesuffix(';'))
    if locations.get('checkpoints'):
        check_url(locations['checkpoints'], terms)
    paths = files_to_publish()
    check_payloads(paths)
    run('git', 'diff', '--check')
    run(sys.executable, 'scripts/check_code_browser.py')
    run(sys.executable, 'scripts/check_publish_page.py')
    run('node', 'scripts/check_code_clearance.js')
    run('node', '--check', 'code/code.js')
    check_archives()
    check_anonymity(terms)
    if not locations.get('checkpoints'):
        print('Checkpoint ZIP: retained locally. Public download stays unavailable until an anonymous URL is configured.', flush=True)
    if not args.push:
        print('Checks complete. No commit or push performed. Browser and external hosting review remain separate.', flush=True)
        return
    if run('git', 'branch', '--show-current', capture=True).stdout.strip() != 'main':
        raise ValueError('Switch to main before publishing')
    # Use the repository-owner account for this subprocess only, without switching
    # the active account globally or placing a token in command arguments.
    token = run('gh', 'auth', 'token', '--hostname', 'github.com', '--user', account, capture=True).stdout.strip()
    if not token:
        raise ValueError('GitHub CLI has no token for the repository-owner account')
    env = dict(os.environ, GH_TOKEN=token, GH_HOST='github.com')
    actor = run('gh', 'api', 'user', '--jq', '.login', capture=True, env=env).stdout.strip()
    if actor.lower() != account.lower():
        raise ValueError('GitHub authentication account does not match the repository owner')
    git = ['git', '-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential']
    run(*git, 'fetch', 'origin', 'main', env=env)
    if run('git', 'merge-base', '--is-ancestor', 'origin/main', 'HEAD', check=False).returncode:
        raise ValueError('Remote main contains changes. Integrate them and rerun; no force push was attempted.')
    run('git', 'add', '--all', '--', '.')
    changed = run('git', 'diff', '--cached', '--quiet', check=False).returncode
    if changed == 1:
        run('git', 'commit', '-m', 'feat: add anonymous code explorer')
    elif changed:
        raise ValueError('Could not inspect staged changes')
    run(*git, 'push', 'origin', 'HEAD:main', env=env)
    local = run('git', 'rev-parse', 'HEAD', capture=True).stdout.strip()
    remote = run(*git, 'ls-remote', 'origin', 'refs/heads/main', capture=True, env=env).stdout.split()[0]
    if remote != local:
        raise ValueError('Remote verification did not match the local commit')
    print('PUSH VERIFIED: main '+local[:12], flush=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print('STOP:', error, file=sys.stderr)
        raise SystemExit(1)
