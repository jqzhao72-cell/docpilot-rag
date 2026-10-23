"""Repository-root launcher: python -m evaluation.run <entrypoint> [arguments]."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
EVALUATION = ROOT / 'evaluation'
PATH_FLAGS = {'--dataset', '--corpus', '--reports-dir', '--run-dir', '--baseline-dir', '--chroma-db'}


def resolve_paths(arguments, cwd):
    """Keep path arguments relative to the caller, not the backend working dir."""
    result = list(arguments)
    for index, arg in enumerate(result):
        name, separator, value = arg.partition('=')
        if name in PATH_FLAGS:
            if separator:
                result[index] = name + '=' + str((cwd / value).resolve())
            elif index + 1 < len(result):
                result[index + 1] = str((cwd / result[index + 1]).resolve())
    return result


def main():
    entries = json.loads((EVALUATION / 'configs/entrypoints.json').read_text(encoding='utf-8'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('entrypoint', choices=sorted(entries))
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    entry = entries[args.entrypoint]
    arguments = resolve_paths(args.arguments, Path.cwd())
    environment = os.environ.copy()
    environment['PYTHONPATH'] = os.pathsep.join([str(ROOT), str(ROOT / 'backend'), environment.get('PYTHONPATH', '')])
    environment['PYTHONIOENCODING'] = 'utf-8'
    command = [sys.executable, '-m', 'evaluation.' + entry['module'], *arguments]
    if not entry['capture'] or any(x in arguments for x in ('-h', '--help')):
        return subprocess.call(command, cwd=ROOT / 'backend', env=environment)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + args.entrypoint + '-' + uuid4().hex[:8]
    output = EVALUATION / 'reports' / entry['category'] / run_id
    output.mkdir(parents=True, exist_ok=False)
    metadata = {'entrypoint': args.entrypoint, 'arguments': arguments, 'status': 'running',
                'started_at_utc': datetime.now(timezone.utc).isoformat(),
                'note': 'Console capture, not an automated answer-quality or faithfulness score.'}
    def save():
        (output / 'run.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    save()
    try:
        with (output / 'stdout.log').open('w', encoding='utf-8') as log:
            with subprocess.Popen(command, cwd=ROOT / 'backend', env=environment,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding='utf-8', errors='replace') as process:
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    print(line, end='', flush=True)
                code = process.wait()
        metadata.update(status='completed' if code == 0 else 'failed', exit_code=code)
    except BaseException:
        metadata['status'] = 'interrupted_or_failed'
        raise
    finally:
        metadata['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save()
        print(f'Report: {output}', flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
