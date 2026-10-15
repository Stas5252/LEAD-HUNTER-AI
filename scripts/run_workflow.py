"""Execute an already imported workflow using the actual n8n CLI."""
from datetime import datetime, timezone
import os
import subprocess
from common import ROOT, compose


def execute(workflow_id):
    # The main process owns 5679. Standalone CLI needs its own task broker.
    log = ROOT / '.local' / ('run-' + workflow_id + '.log')
    with log.open('w') as f:
        os.chmod(log, 0o600)
        r = subprocess.run(['docker', 'compose', 'exec', '-T', '-e', 'N8N_RUNNERS_BROKER_PORT=5680',
                            'n8n', 'n8n', 'execute', '--id=' + workflow_id, '--rawOutput'],
                           cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=1900)
    if r.returncode:
        raise RuntimeError(f'n8n workflow failed; private diagnostic log: {log}')
