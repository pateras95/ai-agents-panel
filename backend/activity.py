"""Build an in-memory stand-up draft from approved local Git repositories."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
import os
from pathlib import Path
import re
import subprocess

from .limits import ATHENS


PROJECTS = {
    "ab-kiosk-app": "AB Kiosk App",
    "ai-assistant-cms": "AI Assistant CMS",
    "ai-assistant-webchat-widget": "AI Assistant Webchat Widget",
    "mailer-panel": "Mailer Panel",
    "transactional-mailer-admin": "Transactional Mailer Admin",
}
ROOT = Path("/var/www/html")


def git(repo, *args, okay=(0,)):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "GIT_NO_LAZY_FETCH": "1"},
        capture_output=True, text=True, errors="replace", timeout=8,
    )
    if result.returncode not in okay:
        raise RuntimeError("Απέτυχε η τοπική ανάγνωση Git.")
    return result.stdout


def collect_project(entry, author, start, end):
    slug, name = entry
    repo = ROOT / slug
    if repo.resolve() != repo or not (repo / ".git").exists():
        raise RuntimeError("Το εγκεκριμένο repo δεν είναι διαθέσιμο.")
    commits = []
    for line in git(
        repo, "log", "--branches", "--remotes",
        "--format=%h%x1f%at%x1f%ae%x1f%P%x1f%s",
    ).split("\n"):
        fields = line.split("\x1f", 4)
        if len(fields) != 5:
            continue
        sha, stamp, email, parents, subject = fields
        if start <= int(stamp) < end and email.casefold() == author:
            commits.append({"sha": sha, "subject": subject[:200],
                            "merge": len(parents.split()) > 1})
    if not commits:
        return None

    pushes = []
    for line in git(
        repo, "reflog", "show", "--all", "--date=unix",
        "--format=%gD%x1f%h%x1f%gs",
    ).split("\n"):
        found = re.fullmatch(r"refs/remotes/([^@]+)@\{(\d+)\}\x1f([^\x1f]+)\x1fupdate by push", line)
        if found and start <= int(found[2]) < end:
            pushes.append({"branch": found[1], "sha": found[3],
                           "time": datetime.fromtimestamp(int(found[2]), ATHENS).strftime("%H:%M")})

    branches = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()
    summary = summarize(commits)
    return {"name": name, "summary": summary, "commits": commits, "branches": branches,
            "pushes": pushes, "source": "Τοπικό Git history, branches και reflog σε ώρα Αθήνας."}


def summarize(commits):
    subjects = list(dict.fromkeys(item["subject"].rstrip(".") for item in commits if not item["merge"]))
    topics = (
        (r"vue\s*3", "μετάβαση σε Vue 3" + (" και Pinia" if "pinia" in " ".join(subjects).lower() else "")),
        (r"users? crud|login|analytics|dashboard", "βελτιώσεις στη διαχείριση χρηστών, στη σύνδεση και στα dashboards"),
        (r"90 days.*csv", "όριο 90 ημερών στην εξαγωγή CSV"),
        (r"jenkins", "ενημέρωση του Jenkins build"),
        (r"node.*version|version.*node", "ενημέρωση της έκδοσης Node.js"),
    )
    combined = "\n".join(subjects).lower()
    matched = [label for pattern, label in topics if re.search(pattern, combined)]
    if matched == ["ενημέρωση της έκδοσης Node.js"] and len(subjects) == 1:
        return "Ενημέρωσα την έκδοση Node.js."
    if len(subjects) == 1:
        if re.search(r"fix.*affinity", combined):
            return "Διόρθωσα τη ρύθμιση affinity."
        if all(word in combined for word in ("demo", "jenkins", "background")):
            return "Πρόσθεσα περιβάλλον demo, νέο Jenkinsfile και νέο φόντο."
        return subjects[0] + "."
    if matched:
        return "Προχώρησα σε " + ", ".join(matched[:-1] or matched) + (
            " και " + matched[-1] if len(matched) > 1 else ""
        ) + "."
    return ", ".join(subjects[:3] or [commits[0]["subject"].rstrip(".")]) + "."


def collect_draft(day, project_root):
    start = datetime.combine(day, time.min, ATHENS).timestamp()
    end = datetime.combine(day + timedelta(days=1), time.min, ATHENS).timestamp()
    author = git(project_root, "var", "GIT_AUTHOR_IDENT").rsplit("<", 1)[-1].split(">", 1)[0].casefold()
    projects, unavailable = [], []
    with ThreadPoolExecutor(max_workers=len(PROJECTS)) as pool:
        jobs = {pool.submit(collect_project, entry, author, start, end): entry[1]
                for entry in PROJECTS.items()}
        for job, name in jobs.items():
            try:
                result = job.result()
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                unavailable.append(name)
                continue
            if result:
                projects.append(result)
    return {"date": day.isoformat(), "projects": projects, "unavailable": unavailable}
