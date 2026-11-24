"""Rewrite stand-up sentences in natural Greek with the user's ChatGPT subscription (Codex CLI).

Only the project name and the commit subjects are sent. No diffs, code, branches or paths. The Codex run is
ephemeral, so no session is stored. Any failure keeps the local rule-based sentence.
"""

import glob
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from threading import Lock, Thread

PROMPT = """Είσαι βοηθός που γράφει το daily stand-up ενός προγραμματιστή στα ελληνικά.
Παίρνεις JSON με projects και τους τίτλους των commits της ημέρας. Για κάθε project γράψε ΜΙΑ φυσική πρόταση
σε πρώτο ενικό παρελθοντικό ("Ολοκλήρωσα…", "Διόρθωσα…"), που εξηγεί το ΑΠΟΤΕΛΕΣΜΑ της δουλειάς με απλά λόγια,
όπως θα το έλεγε σε συνάδελφο ή manager. Όχι λίστα commits, όχι hash, όχι τεχνικές λεπτομέρειες χωρίς λόγο.
Μην επινοείς πράγματα που δεν προκύπτουν από τους τίτλους. Κράτα τα τεχνικά ονόματα (Vue 3, Jenkins, Node.js) όπως είναι.
Απάντησε ΜΟΝΟ με JSON της μορφής {"<όνομα project>": "<πρόταση>"} χωρίς άλλο κείμενο.

"""
CACHE = {}
LOCK = Lock()
WAIT_SECONDS = 14
RETRY_SECONDS = 600


def codex_path():
    found = shutil.which("codex")
    if found:
        return found
    candidates = sorted(glob.glob(os.path.expanduser(
        "~/.cache/JetBrains/*/acp-agents/codex-acp/*/node_modules/.bin/codex")))
    return candidates[-1] if candidates else None


def run(payload):
    binary = codex_path()
    if not binary:
        return {}
    with tempfile.TemporaryDirectory() as work:
        output = os.path.join(work, "answer.txt")
        try:
            subprocess.run(
                [binary, "exec", "--ephemeral", "--skip-git-repo-check", "-s", "read-only",
                 "--color", "never", "-o", output, PROMPT + json.dumps(payload, ensure_ascii=False)],
                cwd=work, stdin=subprocess.DEVNULL, capture_output=True, timeout=90, check=True)
            text = open(output, encoding="utf-8").read().strip()
            text = text[text.index("{"):text.rindex("}") + 1]
            data = json.loads(text)
        except (OSError, ValueError, subprocess.SubprocessError):
            return {}
    return {name: " ".join(sentence.split()) for name, sentence in data.items()
            if isinstance(name, str) and isinstance(sentence, str) and 10 < len(sentence) <= 400}


def humanize(projects, wait=WAIT_SECONDS):
    """Return {project name: Greek sentence}.

    The result is shared by the draft and the week view through one cache, so both show the same text.
    With wait=0 the call never blocks: it starts the job if needed and returns what is already cached.
    A failed job is not retried for ten minutes.
    """
    payload = {"projects": [{"name": item["name"],
                             "commits": [c["subject"] for c in item["commits"] if not c["merge"]][:30]}
                            for item in projects]}
    key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with LOCK:
        job = CACHE.get(key)
        if job and job.get("failed") and time.monotonic() - job["failed"] > RETRY_SECONDS:
            job = None
        if job is None:
            job = CACHE[key] = {"result": None, "failed": 0}

            def work():
                job["result"] = run(payload)
                if not job["result"]:
                    job["failed"] = time.monotonic()
            job["thread"] = Thread(target=work, daemon=True)
            job["thread"].start()
    if wait and job.get("thread") and not job["failed"]:
        job["thread"].join(wait)
    return job["result"] or {}
