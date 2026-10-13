"""Mirror a running training job and publish its matching curves only on completion."""
import argparse,fcntl,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def atomic_json(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)

def watch(run,mirror,pid):
    copied={}
    state=ROOT/'.git/availability-training-monitor.json'
    def backup():
        mirror.mkdir(parents=True,exist_ok=True)
        files=[*run.glob('*.json'),*run.glob('*.jsonl'),*run.glob('*.pt'),run/'console.log']
        for source in files:
            if not source.is_file():continue
            stamp=(source.stat().st_mtime_ns,source.stat().st_size)
            if copied.get(source.name)==stamp:continue
            target=mirror/source.name;tmp=target.with_suffix(target.suffix+'.tmp')
            shutil.copyfile(source,tmp);tmp.replace(target);copied[source.name]=stamp
    try:
        while True:
            backup_error=None
            try:backup()
            except OSError as error:backup_error=str(error)
            progress=json.loads((run/'progress.json').read_text()) if (run/'progress.json').exists() else {}
            status=dict(trainingPid=pid,run=str(run),backup=str(mirror),step=progress.get('step',0),updated=time.time(),backupError=backup_error)
            if (run/'complete.json').exists():
                with (ROOT/'.git/availability-publish.lock').open('w') as lock:
                    fcntl.flock(lock,fcntl.LOCK_EX)
                    for command in [[sys.executable,'scripts/export_availability_losses.py',str(run)],
                                    [sys.executable,'scripts/build_asset_revisions.py'],
                                    [sys.executable,'scripts/build_site_bundle.py']]:
                        subprocess.run(command,cwd=ROOT,check=True)
                atomic_json(state,dict(status,status='complete',localGraphsPublished=True))
                print('Training complete; local loss graphs published.',flush=True);return
            try:os.kill(pid,0)
            except ProcessLookupError:
                raise RuntimeError('Training process exited before complete.json; see console.log')
            atomic_json(state,dict(status,status='training',localGraphsPublished=False))
            time.sleep(30)
    except Exception as error:
        atomic_json(state,dict(status='error',error=str(error),run=str(run),backup=str(mirror),updated=time.time()))
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--mirror',type=Path,required=True);p.add_argument('--pid',type=int,required=True)
    a=p.parse_args();watch(a.run,a.mirror,a.pid)
