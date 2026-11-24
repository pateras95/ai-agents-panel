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
    # Personal projects on GitHub, approved by the user.
    "ai-agents-panel": "NEXUS AI",
    "gaby-portofolio": "Gaby Portfolio",
}
PERSONAL = {"ai-agents-panel", "gaby-portofolio"}
CATEGORIES = {name: "personal" if slug in PERSONAL else "mpass" for slug, name in PROJECTS.items()}
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


def collect_project(entry, start, end):
    slug, name = entry
    repo = ROOT / slug
    if repo.resolve() != repo or not (repo / ".git").exists():
        raise RuntimeError("Το εγκεκριμένο repo δεν είναι διαθέσιμο.")
    author = git(repo, "var", "GIT_AUTHOR_IDENT").rsplit("<", 1)[-1].split(">", 1)[0].casefold()
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
    return {"name": name, "category": CATEGORIES[name], "summary": summary, "commits": commits, "branches": branches,
            "pushes": pushes, "source": "Τοπικό Git history, branches και reflog σε ώρα Αθήνας."}


VERBS = (
    (r"^(add|added|adds|create|created|implement|introduce|new)\b", "πρόσθεσα"),
    (r"^(fix|fixed|fixes|hotfix|bugfix|patch|resolve)\b", "διόρθωσα"),
    (r"^(remove|removed|delete|deleted|drop|clean|cleanup)\b", "αφαίρεσα"),
    (r"^(refactor|improve|improved|optimi[sz]e|simplify|polish)\b", "βελτίωσα"),
    (r"^(revert)\b", "επανέφερα"),
    (r"^(rename|move|moved)\b", "μετέφερα"),
    (r"^(update|updated|change|changed|bump|upgrade|modify|set|edit|adjust|tweak)\b", "ενημέρωσα"),
)
# Greek accusative phrases, the first matching entry wins.
OBJECTS = (
    (r"vue\s*3|vue3", "το project σε Vue 3"),
    (r"node.*version|version.*node", "την έκδοση του Node.js"),
    (r"jenkins\s*file|jenkinsfile", "το Jenkinsfile"),
    (r"jenkins", "το Jenkins build"),
    (r"docker", "τη ρύθμιση Docker"),
    (r"pinia", "το Pinia"),
    (r"users? crud|users?\b", "τη διαχείριση χρηστών"),
    (r"login|logout|auth", "τη σύνδεση χρηστών"),
    (r"analytics|dashboards?", "τα dashboards"),
    (r"90 days.*csv|csv", "την εξαγωγή CSV"),
    (r"affinity", "τη ρύθμιση affinity"),
    (r"\bpath\b", "τη διαδρομή (path)"),
    (r"background|\bbg\b", "το φόντο"),
    (r"\bdemo\b", "το περιβάλλον demo"),
    (r"css|style|theme", "την εμφάνιση (στυλ)"),
    (r"\btests?\b|spec", "τα τεστ"),
    (r"readme|docs?\b|documentation", "την τεκμηρίωση"),
    (r"config|settings?|env\b", "τη διαμόρφωση"),
    (r"dependenc|package|npm|yarn", "τις εξαρτήσεις"),
    (r"\bapi\b|endpoint", "το API"),
    (r"build|pipeline|\bci\b", "το build"),
    (r"layout|\bui\b|design|responsive", "το UI"),
    (r"migration|database|\bdb\b|sql", "τη βάση δεδομένων"),
    (r"e-?mail|mailer|smtp", "το σύστημα email"),
    (r"translat|i18n|locale|\blang", "τις μεταφράσεις"),
    (r"version", "την έκδοση"),
)
GENERIC_SUBJECT = re.compile(r"^(merge|merged in|merge branch|merge pull request)\b", re.I)


def join_greek(parts):
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " και " + parts[-1]


def summarize(commits):
    """Greek one-sentence outcome from commit subjects, using only local rule-based text."""
    subjects = list(dict.fromkeys(item["subject"].rstrip(".").strip()
                                  for item in commits if not item["merge"]))
    subjects = [text for text in subjects if text and not GENERIC_SUBJECT.match(text)]
    if not subjects:
        return "Συγχώνευσα αλλαγές μεταξύ branches."
    groups, seen = {}, set()
    for subject in subjects:
        lowered = subject.lower()
        verb = next((word for pattern, word in VERBS if re.search(pattern, lowered)), None)
        thing = next((word for pattern, word in OBJECTS if re.search(pattern, lowered)), None)
        if thing is None:
            thing = "«" + subject[:60] + "»"
            verb = verb or "δούλεψα πάνω στο"
        elif verb is None:
            verb = "ενημέρωσα"
        if "Vue 3" in thing:
            verb = "μετέφερα"
        if thing in seen:
            continue
        seen.add(thing)
        groups.setdefault(verb, []).append(thing)
    clauses = [f"{verb} {join_greek(things[:4])}" for verb, things in groups.items()]
    sentence = join_greek(clauses)
    return sentence[0].upper() + sentence[1:] + "."


def collect_draft(day, project_root, humanized=False):
    start = datetime.combine(day, time.min, ATHENS).timestamp()
    end = datetime.combine(day + timedelta(days=1), time.min, ATHENS).timestamp()
    projects, unavailable = [], []
    with ThreadPoolExecutor(max_workers=len(PROJECTS)) as pool:
        jobs = {pool.submit(collect_project, entry, start, end): entry[1]
                for entry in PROJECTS.items()}
        for job, name in jobs.items():
            try:
                result = job.result()
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                unavailable.append(name)
                continue
            if result:
                projects.append(result)
    if humanized and projects:
        from .humanize import humanize
        rewritten = humanize(projects, wait=0 if humanized == "cached" else 14)
        for project in projects:
            if project["name"] in rewritten:
                project["summary"] = rewritten[project["name"]]
                project["source"] += " Η διατύπωση έγινε με ChatGPT από τίτλους commits."
    return {"date": day.isoformat(), "projects": projects, "unavailable": unavailable, "categories": CATEGORIES}
