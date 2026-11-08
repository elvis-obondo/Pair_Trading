"""Repo cleanup, Step 1: inventory only (brief, 2026-11-07, docs/prompts/REPO_CLEANUP.md). Deletes
nothing. Walks the whole repo, measures every candidate's size and git status with real commands (never
estimated), and writes docs/CLEANUP_INVENTORY.md. Every number in that file is printed by this script
(CLAUDE.md standing rule, 2026-11-07).

    python3 -u scripts/cleanup_inventory.py > research/dataset/logs/cleanup_inventory.log

Protected (never listed, per the brief): anything cited as a receipt by research/dislocation_model/
NUMBERS.md, by docs/HYPERLIQUID_HANDOFF.md or docs/PLANNER_HANDOFF.md (the decisions log / planner's
files), or by any docs/prompts/*.md brief -- citation is checked by substring search of each
candidate's repo-relative path and basename against those documents' text, not asserted by hand. Also
protected: CLAUDE.md, docs/prompts/BUILDER_HANDOFF.md (a role handoff), research/datasets/ (the v1
dataset and its manifest), and NUMBERS.md itself.

Classification is rule-based and each rule is named in the output so a human can check it. Where a
whole directory's files all share one reason, this emits ONE row for the directory (per the brief:
"One row per candidate, either a file or a whole folder where everything in it shares one reason").
This script does NOT try to enumerate every one of the ~700 tracked source/pipeline files individually
-- those are not cleanup candidates and including them would bury the real candidates. It targets:
known bulk directories (caches, archives, old experiment scratch), files/dirs matching one-off launch/
probe naming patterns, docs/prompts/*.md briefs not cited anywhere, and loose top-level files not
referenced anywhere in the repo's own text. Anything it is NOT confident about is still listed, with
`reason` stating the uncertainty plainly, rather than silently omitted or silently guessed.
"""
import fnmatch
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_MD = os.path.join(ROOT, "docs", "CLEANUP_INVENTORY.md")

# ---------------------------------------------------------------------------
# Git helpers -- every status/size/commit figure comes from one of these.
# ---------------------------------------------------------------------------

def run(cmd, cwd=ROOT):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.stdout


def git_tracked_files():
    return set(run(["git", "ls-files"]).splitlines())


def git_untracked_not_ignored():
    out = run(["git", "status", "--porcelain"])
    return {line[3:] for line in out.splitlines() if line.startswith("??")}


def git_ignored_paths():
    out = run(["git", "status", "--porcelain", "--ignored"])
    return {line[3:].rstrip("/") for line in out.splitlines() if line.startswith("!!")}


def git_last_commit(path):
    out = run(["git", "log", "-1", "--format=%h %ad %s", "--date=short", "--", path])
    return out.strip() or None


def path_size_bytes(path):
    full = os.path.join(ROOT, path)
    if os.path.isfile(full):
        return os.path.getsize(full)
    total = 0
    for dirpath, _, filenames in os.walk(full):
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}TB"


def check_recoverable(path):
    """Checker's fix 2: 'untracked' does not always mean 'lost for good' -- a file can be byte-
    identical to a version git already has in history (even if the path is untracked NOW). Checks
    every commit that ever touched this exact path (`git log --all -- path`), compares that commit's
    content hash to the current file's, and returns the short sha of the first exact match, or None.
    Only meaningful for a single file (not a directory); callers skip this for directories. This does
    NOT check S3 -- the brief's 'not in git or S3' definition is only half-checked here, so every
    UNTRACKED DATA risk line still says 'S3 not checked', not a clean 'lost for good'."""
    import hashlib
    full = os.path.join(ROOT, path)
    if not os.path.isfile(full):
        return None
    cur_hash = hashlib.sha256(open(full, "rb").read()).hexdigest()
    commits = run(["git", "log", "--all", "--format=%H", "--", path]).splitlines()
    for c in commits:
        r = subprocess.run(["git", "show", f"{c}:{path}"], cwd=ROOT, capture_output=True)
        if r.returncode == 0 and hashlib.sha256(r.stdout).hexdigest() == cur_hash:
            return c[:7]
    return None


def untracked_risk(path, files=None):
    """Checks every file under `path` (itself, if a file; every file inside, if a directory -- or, if
    `files` is given explicitly, exactly that list and nothing else, e.g. only the UNTRACKED half of a
    mixed pilot directory, not its tracked metadata files too) for git-history recoverability
    (check_recoverable), and returns (risk_text, lost_size_bytes) -- lost_size is the precise byte
    total of files with NO identical git history found, so a directory that mixes recoverable and
    non-recoverable files (research/live_archive: one file matches commit 6885e35 exactly, per the
    Checker's own check; the other does not) reports an accurate size, not an all-or-nothing guess.
    Round-5: S3 is now checked too (s3_check, one cached `aws s3 ls --recursive` call), so the risk
    text states a real finding instead of the old blanket 'S3 not checked' -- the 3rd return value is
    (s3_status, s3_detail) for the 'in S3' column."""
    if files is None:
        full = os.path.join(ROOT, path)
        files = [path] if os.path.isfile(full) else [
            os.path.relpath(os.path.join(dp, fn), ROOT) for dp, _, fns in os.walk(full) for fn in fns]
    s3_listing()  # populate S3_CHECK_FAILED as a side effect
    s3_keys = set(S3_KEYS)
    lost_size, recov_size, s3_size, recov_commits, s3_examples = 0, 0, 0, set(), []
    for f in files:
        sz = os.path.getsize(os.path.join(ROOT, f))
        c = check_recoverable(f)
        if c:
            recov_size += sz
            recov_commits.add(c)
        elif f in s3_keys:
            # exact repo-relative path == S3 key only -- NOT the directory-level fuzzy basename
            # match s3_check() does (that matched attic/okx_data/.DS_Store, a trivial macOS artifact
            # under an S3 prefix that turned out to hold an unrelated old snapshot, and reported a
            # misleading "yes" for the row's REAL data, which has zero exact-path matches). Only an
            # exact per-file path hit counts as "recoverable from S3" here, so this number can never
            # contradict the display column below -- they come from the same computation.
            s3_size += sz
            if len(s3_examples) < 3:
                s3_examples.append(f)
        else:
            lost_size += sz
    if S3_CHECK_FAILED:
        s3_status, s3_detail = "not checked", "aws s3 ls failed"
    elif s3_size > 0:
        s3_status, s3_detail = "yes", f"{len(s3_examples)}+ exact path match(es), e.g. {s3_examples[0]}"
    else:
        s3_status, s3_detail = "no", None
    s3_note = {"yes": f"in S3 ({s3_detail})",
               "no": f"no (not at the same path, checked against {len(s3_keys)} objects in "
                     f"s3://{S3_BUCKET}/)",
               "not checked": "S3 not checked (aws s3 ls failed)"}[s3_status]
    if not files:
        return "", 0, (s3_status, s3_detail)
    parts = []
    if recov_size:
        parts.append(f"{human(recov_size)} recoverable from git history (commit(s) "
                      f"{', '.join(sorted(recov_commits))})")
    if s3_size:
        parts.append(f"{human(s3_size)} recoverable from S3 (exact path match, not git)")
    if lost_size:
        parts.append(f"{human(lost_size)} UNTRACKED DATA with no identical copy found in git history "
                      f"or S3")
    if lost_size == 0:
        risk = f"untracked, fully recoverable ({'; '.join(parts)}); {s3_note}"
    elif recov_size == 0 and s3_size == 0:
        risk = f"UNTRACKED DATA -- lost for good if deleted (no identical git history or S3 copy found); {s3_note}"
    else:
        risk = f"MIXED: {'; '.join(parts)}; {s3_note}"
    return risk, lost_size, (s3_status, s3_detail)


# ---------------------------------------------------------------------------
# S3 check -- round-5 fix (planner + Checker): each untracked-data row gets a real, read-only
# `aws s3 ls` check against the project's own backup bucket, not just "S3 not checked" prose.
# ---------------------------------------------------------------------------

S3_BUCKET = "pair-trading-hl-289869684922"
S3_KEYS = None  # filled by s3_listing(): the one recursive `aws s3 ls` call, cached for every row
S3_CHECK_FAILED = False


def s3_listing():
    global S3_KEYS, S3_CHECK_FAILED
    if S3_KEYS is not None:
        return S3_KEYS
    cmd = ["aws", "s3", "ls", "--recursive", f"s3://{S3_BUCKET}/"]
    print(f"[CLEANUP-INV] S3 check: `{' '.join(cmd)}` (one call, cached for every row below)",
          flush=True)
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        print(f"[CLEANUP-INV] S3 check FAILED (exit {out.returncode}): {out.stderr.strip()[:200]} "
              f"-- every row's 'in S3' will read 'not checked (aws s3 ls failed)'.", flush=True)
        S3_CHECK_FAILED = True
        S3_KEYS = []
        return S3_KEYS
    # each line: "<date> <time> <size> <key>" -- key is everything from the 4th field on
    keys = []
    for line in out.stdout.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4:
            keys.append(parts[3])
    S3_KEYS = keys
    print(f"[CLEANUP-INV] S3 check: {len(S3_KEYS)} objects listed under s3://{S3_BUCKET}/", flush=True)
    return S3_KEYS


def git_status_of(path):
    tracked, untracked, ignored = git_tracked_files(), git_untracked_not_ignored(), git_ignored_paths()
    if path in tracked or any(t.startswith(path + "/") for t in tracked):
        return "tracked"
    if path in ignored or any(path.startswith(i + "/") or i.startswith(path + "/") for i in ignored):
        return "ignored (untracked data if deleted)"
    if path in untracked or any(u.startswith(path + "/") for u in untracked):
        return "untracked, not ignored (untracked data if deleted)"
    return "unknown"


# ---------------------------------------------------------------------------
# Citation search -- is `path` referenced as a receipt by a live document?
# ---------------------------------------------------------------------------

CITING_DOCS = None  # filled in main(): {doc_path: lines-list}
DOCS_USED_AS_CITATION_SOURCE = set()  # filled by is_cited(): docs that protected >=1 other candidate
PROTECTED_LOG = []  # (candidate_path, citing_doc, line_no, matched_token, line_text) -- audit trail

TOKEN_RE = re.compile(r"[A-Za-z0-9_./*-]+")   # a path-like run; "." and "/" stay IN the token on
# purpose, and "*" is included too (round-3 bugfix: without it, a glob like "aws_s1_*" would be
# truncated to "aws_s1_" at the "*" and rule 3 -- which checks for "*" in the token -- could never
# fire at all; the "*.log"/bare-glob exclusion in rule 3 still works, since it also requires "/").


def _line_tokens(line):
    """Checker's round-4 fix: "." stays IN the token class on purpose (it's part of a file extension),
    but that means a token at the end of a sentence carries the full stop too -- "its tree is in
    attic/vm_final." tokenizes as "attic/vm_final." (with the period attached), which then matches
    nothing. Strip sentence/bracket punctuation from both ends of each token after extraction. A
    single trailing "." is safe to strip even though "." is meaningful mid-token (a real path never
    ends in a bare "." with nothing after it)."""
    return [t.strip(".,;:)]'\"([") for t in TOKEN_RE.findall(line)]


def is_cited(path):
    """Checker's round-3 rule, replacing substring matching entirely (round 2's substring+length-
    threshold version still matched a bare `*.log` glob against every log in the repo, matched a
    shorter cited name as a substring of an unrelated longer one -- master_funding.log "inside"
    master_funding_check.log -- and matched a cited FILE as if it protected its containing directory).
    Tokens are extracted from each citing line with TOKEN_RE (a run of [A-Za-z0-9_./-] -- this keeps
    "." and "/" IN the token, so "master_funding.log" and "master_funding_check.log" are two distinct
    tokens that can never equal or substring-match each other, and a bare "*.log"/"*" token with no
    "/" is just a token, never treated as a glob). A candidate is protected only if some token:
    1. equals `path`, or is a suffix of `path` landing exactly on a "/" boundary (e.g. the token
       "hyperliquid/logs/build5_pilot.log" matches the fuller candidate path
       "research/hyperliquid/logs/build5_pilot.log" -- the character just before the suffix is "/");
    2. for a FILE candidate only, equals its bare basename (extension included) exactly;
    3. contains both "*" and "/" (a real glob, not a bare extension pattern) and `fnmatch`es `path`
       directly (never basename-to-basename -- that was round 2's bug: `scripts/gcp_*` doesn't match
       `research/hyperliquid/logs/gcp_import_check.log` as a full path, so it no longer protects it,
       even though the two share a "gcp_*" basename shape).
    A directory candidate is protected by rule 1 only (a mention with at least one parent component,
    or a trailing "/") -- never by a bare basename alone (rule 2 is files-only), so a citation of a
    FILE inside a directory does not, by itself, protect the directory. The matched token itself is
    recorded in PROTECTED_LOG, alongside the doc/line, for audit.

    Round-5 (planner's ruling): a citation no longer EXCLUDES a candidate from the list -- it only
    ANNOTATES it. Every candidate is listed regardless; a hit here is shown as a "cited by <doc:line>"
    column so the user can see the citation and still decide to delete it. Returns "doc:line" (not
    just doc) so that column can be printed directly."""
    is_dir = os.path.isdir(os.path.join(ROOT, path))
    base = os.path.basename(path)
    for doc, lines in CITING_DOCS.items():
        for i, line in enumerate(lines, start=1):
            for tok in _line_tokens(line):
                matched = False
                # rule 3: a real glob (both "*" and "/"), fnmatch against the FULL path only
                if "*" in tok and "/" in tok and fnmatch.fnmatch(path, tok):
                    matched = True
                # rule 1: exact path, or a MULTI-COMPONENT suffix landing on a "/" boundary (trailing
                # "/" normalised away first, so "attic/okx_data/" matches the directory
                # "attic/okx_data"). A bare single-word token with no "/" anywhere (e.g.
                # "build7_oipilot") does NOT qualify here even if it happens to equal the candidate's
                # last path component -- that's rule 2's job, and rule 2 is files-only, so a bare
                # directory-name mention with no parent component and no trailing "/" protects
                # nothing (round-3 fix: this previously let a bare basename sneak through rule 1).
                tok_n = tok.rstrip("/")
                had_trailing_slash = tok != tok_n
                has_parent = "/" in tok_n
                if tok_n and (path == tok_n or
                              ((has_parent or had_trailing_slash) and path.endswith(tok_n) and
                               len(path) > len(tok_n) and path[-(len(tok_n) + 1)] == "/")):
                    matched = True
                # rule 4 (round-4 fix): a citation of a FILE INSIDE a directory candidate protects the
                # directory -- e.g. NUMBERS.md's receipt for attic/vm_final/vm_final_20261014.tar.gz
                # (a specific archived file, with its own sha256 checked both sides) is a receipt FOR
                # the attic/vm_final/ directory it lives in, not just for that one file in isolation.
                # Only fires for directories, and only when the token is a path genuinely nested under
                # this one (starts with "<path>/"), not a same-prefix sibling file (e.g. a log file
                # named similarly to a directory does NOT trigger this).
                if is_dir and tok_n.startswith(path + "/"):
                    matched = True
                # rule 2: bare basename, files only, exact token match
                if not is_dir and tok == base:
                    matched = True
                if matched:
                    PROTECTED_LOG.append((path, doc, i, tok, line.strip()))
                    DOCS_USED_AS_CITATION_SOURCE.add(doc)
                    return f"{doc}:{i}"
    return None


def grep_whole_repo(needle, exclude_path=None):
    """git grep for `needle` across tracked files (fast, respects .gitignore). Returns matching paths,
    excluding `exclude_path` itself. Used for the orphan check: nothing imports/calls/cites it."""
    out = run(["git", "grep", "-l", "-F", needle])
    hits = [l for l in out.splitlines() if l and l != exclude_path]
    return hits


# ---------------------------------------------------------------------------
# Main inventory
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    print(f"[CLEANUP-INV] start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}",
          flush=True)
    import hashlib
    sha = hashlib.sha256(open(__file__, "rb").read()).hexdigest()
    print(f"[CLEANUP-INV] sha256 scripts/cleanup_inventory.py: {sha}", flush=True)

    global CITING_DOCS
    # Checker's fix 3: the first pass's citing-doc set missed docs/VM_HANDOFF.md (which is what cites
    # research/live_archive), docs/DATASET_DICTIONARY.md (the v1 dataset's own doc), docs/CLOUD_DEPLOY.md
    # and docs/STRATEGY_SUMMARY.md. All four added; every other .md directly under docs/ (not
    # docs/prompts/) is also swept in automatically below, so nothing under docs/ is excluded by name.
    citing_paths = ["research/dislocation_model/NUMBERS.md"]
    docs_dir = os.path.join(ROOT, "docs")
    for fn in sorted(os.listdir(docs_dir)):
        full = os.path.join(docs_dir, fn)
        if os.path.isfile(full) and fn.endswith(".md") and fn != "CLEANUP_INVENTORY.md":
            citing_paths.append(os.path.join("docs", fn))
    prompts_dir = os.path.join(docs_dir, "prompts")
    for fn in sorted(os.listdir(prompts_dir)):
        if fn.endswith(".md"):
            citing_paths.append(os.path.join("docs", "prompts", fn))
    CITING_DOCS = {}
    for p in citing_paths:
        full = os.path.join(ROOT, p)
        if os.path.exists(full):
            CITING_DOCS[p] = open(full, encoding="utf-8", errors="replace").read().splitlines()
    print(f"[CLEANUP-INV] citation set built from {len(CITING_DOCS)} documents: "
          f"{', '.join(sorted(CITING_DOCS))}", flush=True)

    rows = []   # dict: path, size_bytes, git_status, last_commit, reason, risk, evidence

    def add(path, reason, evidence):
        # Round-5: planner's ruling overrides the brief's "never list a cited receipt" clause for
        # known bulk items (attic/*, research/exit_study, research/live_archive) -- a citation is
        # shown, never used to hide a row, so the user sees it and decides. cited_by is "doc:line" or
        # None.
        cited_by = is_cited(path)
        size = path_size_bytes(path)
        status = git_status_of(path)
        commit = git_last_commit(path) if "tracked" in status else None
        risk, lost_size, s3 = "", 0, None
        if "untracked" in status or "ignored" in status:
            risk, lost_size, s3 = untracked_risk(path)
        rows.append({"path": path, "size": size, "status": status, "commit": commit,
                     "reason": reason, "evidence": evidence, "risk": risk, "lost_size": lost_size,
                     "cited_by": cited_by, "s3": s3})
        cite_note = f" | cited by {cited_by}" if cited_by else ""
        print(f"[CLEANUP-INV] candidate: {path} | {human(size)} | {status} | {reason} | "
              f"risk={risk or '-'}{cite_note}", flush=True)

    # ---- attic/ -- heterogeneous, so checked per immediate child, not as one bulk row (the brief
    # requires everything in a one-row folder to share ONE reason; attic's own children do not: some
    # subpaths are cited by live build briefs, others are not). ----
    attic_dir = os.path.join(ROOT, "attic")
    if os.path.isdir(attic_dir):
        for child in sorted(os.listdir(attic_dir)):
            rel = os.path.join("attic", child)
            if child in ("okx_data", "vm_final"):
                add(rel, "orphan",
                    f"orphan IN CODE (nothing imports or runs it): untracked (git status --ignored "
                    f"shows '{rel}/' as '!!'); `git grep -l {child}` over tracked files finds nothing "
                    f"that reads from this path -- not an input to any live script. It may still be "
                    f"cited as a RECEIPT in prose elsewhere (see the 'cited by' column) -- that is a "
                    f"documentation mention, not a code dependency, and the two are checked "
                    f"separately.")
            else:
                add(rel, "superseded",
                    f"the project's 'delete, don't attic' standing rule (CLAUDE.md) replaces the need "
                    f"for an archive directory -- git history is the attic. This subpath was checked "
                    f"for citation individually (not assumed from attic/'s own reputation); if it is "
                    f"listed below as a candidate, no live brief/NUMBERS.md/decisions-log citation was "
                    f"found for it.")
    # Checker's fix: these two evidence strings used to be typed prose asserting a grep result without
    # actually running one -- replaced with a real grep_whole_repo() call each, so the claim matches
    # what was actually computed (this doesn't replace the is_cited() protection check above, which
    # still runs first inside add() -- it only supplies the EVIDENCE text for whichever of these
    # survives as an actual candidate).
    exit_study_hits = grep_whole_repo("exit_study")
    add("research/exit_study", "orphan",
        f"orphan IN CODE (nothing imports or runs it): entirely untracked and gitignored (git status "
        f"--ignored shows 'research/exit_study/'); `git grep -l -F \"exit_study\"` over tracked files "
        f"returns {len(exit_study_hits)} hit(s)"
        f"{(': ' + ', '.join(exit_study_hits)) if exit_study_hits else ' -- nothing reads from this directory'}."
        f" May still be cited as a RECEIPT in prose elsewhere (see 'cited by') -- a documentation "
        f"mention, not a code dependency.")
    live_archive_hits = grep_whole_repo("live_archive")
    add("research/live_archive", "orphan",
        f"orphan IN CODE (nothing imports or runs it): untracked, not gitignored; `git grep -l -F "
        f"\"live_archive\"` over tracked files returns {len(live_archive_hits)} hit(s)"
        f"{(': ' + ', '.join(live_archive_hits)) if live_archive_hits else ' -- nothing reads from this directory'}."
        f" May still be cited as a RECEIPT in prose elsewhere (see 'cited by') -- a documentation "
        f"mention, not a code dependency.")
    # Planner's updated brief (round 5, superseding Checker's fix 1 of re-labeling it): .venv/ is
    # never listed at all and is out of every total -- not a candidate row, not a __pycache__-style
    # "generated" row either. Nothing added here on purpose.
    print(f"[CLEANUP-INV] .venv not listed (planner's brief: never listed, out of every total); "
          f"size for reference only: {human(path_size_bytes('.venv'))}", flush=True)
    add("user_data/data", "orphan",
        "orphan IN CODE (nothing in this script's own grep sweep imports or runs it): untracked, "
        "180MB. Not flagged with confidence -- this looks like freqtrade-style live-trading data, not "
        "a research artifact, and it was NOT grepped against the trading bot's own runtime config (out "
        "of this script's scope). It may still be cited as a receipt elsewhere (see 'cited by') -- a "
        "documentation mention, not a code dependency. Needs a human call, not an automated one, "
        "before any deletion.")
    add("user_data/normalized", "orphan",
        "untracked, 50MB. Same caveat as user_data/data above -- not flagged with confidence, needs a "
        "human call.")

    # ---- __pycache__ (collapsed to one row; many small dirs, all generated, all gitignored) ----
    pycache_dirs = []
    for dirpath, dirnames, _ in os.walk(ROOT):
        if ".git" in dirpath.split(os.sep):
            continue
        if "__pycache__" in dirnames:
            pycache_dirs.append(os.path.relpath(os.path.join(dirpath, "__pycache__"), ROOT))
    pycache_total = sum(path_size_bytes(p) for p in pycache_dirs)
    # Checker's fix 5: is .venv's own bytecode cache included? Yes -- os.walk starts at ROOT and
    # descends into .venv like any other directory. Split the total so the project-code share (the
    # part actually worth noting) isn't hidden inside the venv's much larger share.
    venv_pycache = [p for p in pycache_dirs if p.startswith(".venv" + os.sep)]
    venv_pycache_size = sum(path_size_bytes(p) for p in venv_pycache)
    project_pycache_size = pycache_total - venv_pycache_size
    print(f"[CLEANUP-INV] {len(pycache_dirs)} __pycache__ directories found, total "
          f"{human(pycache_total)}, all gitignored -- of which {len(venv_pycache)} dirs / "
          f"{human(venv_pycache_size)} are inside .venv (the venv's own bytecode, included in the "
          f"total), and {len(pycache_dirs)-len(venv_pycache)} dirs / {human(project_pycache_size)} "
          f"are this project's own code.", flush=True)
    rows.append({"path": f"{len(pycache_dirs)} __pycache__ directories (listed in the log; "
                f"{human(venv_pycache_size)} of this is .venv's own bytecode, "
                f"{human(project_pycache_size)} is project code)",
                "size": pycache_total, "status": "ignored (generated, not data -- regenerable)",
                "commit": None, "reason": "generated",
                "evidence": "Python bytecode cache; rebuild by importing the module again. All "
                             "gitignored already (git status --ignored).",
                "risk": "", "lost_size": 0})

    # ---- One-off launch/probe scripts and their logs, across every research/**/logs dir (planner's
    # fix 1/3: the first pass only looked at research/model/, missing research/dataset/logs/ and
    # research/hyperliquid/logs/ one-off output entirely -- e.g. chain24_launch*.log, master_chain24_
    # done.log, master_chain_24.log, master_manifest_v1.log). ----
    oneoff_patterns = re.compile(
        r"(probe|dryrun|_launch|wrapper|userdata|one_fit|sizing_wrapper|_check\d*\.log$|chain_?24|"
        r"missing_minutes)", re.I)
    # Planner's round-5 brief: research/dataset/logs/master_manifest_v1.log is the v1 freeze's own
    # provenance receipt, to be added to git in Step 2 -- not a one-off candidate, so it's named here
    # explicitly rather than left to match the pattern above (it no longer does, since
    # "master_manifest_v1" was removed from oneoff_patterns, but this exclude_files entry is kept as
    # a second, explicit guard in case any other pattern above ever broadens to catch it again).
    exclude_files = {"s1_run.py", "s1_preprocess.py", "harness.py", "cleanup_inventory.log",
                      "master_manifest_v1.log"}
    model_dir = os.path.join(ROOT, "research", "model")
    oneoff_hits = []
    if os.path.isdir(model_dir):
        for fn in sorted(os.listdir(model_dir)):
            full = os.path.join(model_dir, fn)
            if os.path.isfile(full) and oneoff_patterns.search(fn) and fn not in exclude_files:
                oneoff_hits.append(os.path.join("research", "model", fn))
    for logs_root in ("research/model/logs", "research/dataset/logs", "research/hyperliquid/logs"):
        logs_dir = os.path.join(ROOT, logs_root)
        if os.path.isdir(logs_dir):
            for fn in sorted(os.listdir(logs_dir)):
                full = os.path.join(logs_dir, fn)
                if os.path.isfile(full) and oneoff_patterns.search(fn) and fn not in exclude_files:
                    oneoff_hits.append(os.path.join(*logs_root.split("/"), fn))
    for p in oneoff_hits:
        add(p, "one-off",
            f"filename matches a launch/probe/dry-run naming pattern ({oneoff_patterns.pattern}); "
            f"a finished sizing/probe/chain-run helper or its log, superseded by the production "
            f"pipeline script it was launching.")

    # ---- Build pilot/launch output directories (research/hyperliquid/logs/) -- MIXED: each one holds
    # a handful of tracked small metadata/log/text files alongside large untracked .parquet data files.
    # A single bulk row (like the earlier attic/ mistake) would report the whole thing as "tracked" and
    # hide the untracked-data risk on the big files -- so each is split into its tracked and untracked
    # parts, sized and flagged separately, both still one bulk row each (not one row per parquet file). ----
    tracked_set = git_tracked_files()
    for pilot_dir, origin in (("research/hyperliquid/logs/build5_pilot", "build5 (wallet tables)"),
                               ("research/hyperliquid/logs/build7_oipilot", "build7 (OI pilot)")):
        full = os.path.join(ROOT, pilot_dir)
        if not os.path.isdir(full):
            continue
        cited_by = is_cited(pilot_dir)  # round-5: annotate only, never skip
        tracked_files, untracked_files = [], []
        for dirpath, _, filenames in os.walk(full):
            for fn in filenames:
                rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
                (tracked_files if rel in tracked_set else untracked_files).append(rel)
        if tracked_files:
            sz = sum(os.path.getsize(os.path.join(ROOT, p)) for p in tracked_files)
            commit = git_last_commit(tracked_files[0])
            rows.append({"path": f"{pilot_dir} (tracked part: {len(tracked_files)} metadata/log files)",
                        "size": sz, "status": "tracked", "commit": commit, "reason": "generated",
                        "risk": "", "lost_size": 0, "cited_by": cited_by, "s3": None,
                        "evidence": f"small metadata/stdout/timing files from {origin}'s one-off "
                                     f"pilot run, committed alongside the (untracked) data files below."})
            print(f"[CLEANUP-INV] candidate: {pilot_dir} (tracked part) | {human(sz)} | tracked | "
                  f"generated", flush=True)
        if untracked_files:
            sz = sum(os.path.getsize(os.path.join(ROOT, p)) for p in untracked_files)
            risk, lost_size, s3 = untracked_risk(pilot_dir, files=untracked_files)
            rows.append({"path": f"{pilot_dir} (untracked part: {len(untracked_files)} data files, "
                        f"mostly .parquet)", "size": sz,
                        "status": "untracked, not ignored (untracked data if deleted)", "commit": None,
                        "reason": "generated", "risk": risk, "lost_size": lost_size,
                        "cited_by": cited_by, "s3": s3,
                        "evidence": f"the actual pilot-run data output from {origin}'s one-off sizing "
                                     f"run (wallet/OI/vault tables for a handful of sample days); "
                                     f"rebuild by rerunning that build step against the same historical "
                                     f"inputs -- NOT verified here that those exact historical inputs "
                                     f"are still re-fetchable, so treated as untracked data, not as "
                                     f"freely regenerable."})
            print(f"[CLEANUP-INV] candidate: {pilot_dir} (untracked part) | {human(sz)} | untracked | "
                  f"generated | risk={risk}", flush=True)

    # ---- Top-level loose files: orphan check via git grep ----
    for fn in ("Dockerfile.trading", "docker-compose.trading.yml", "docker-compose.yml",
               "APE_DOGE_Spread_Trade.docx"):
        full = os.path.join(ROOT, fn)
        if not os.path.exists(full):
            continue
        hits = grep_whole_repo(fn, exclude_path=fn)
        if not hits:
            add(fn, "orphan", f"`git grep -l -F \"{fn}\"` (excluding itself) returns no tracked file "
                f"that references it.")
        else:
            print(f"[CLEANUP-INV] NOT a candidate: {fn} is referenced by {hits}", flush=True)
    full = os.path.join(ROOT, "dashboard")
    if os.path.isdir(full):
        hits = grep_whole_repo("dashboard/")
        if not hits:
            add("dashboard", "orphan", "`git grep -l -F \"dashboard/\"` returns no tracked file that "
                "references this directory.")

    # ---- Tracked code orphan check (planner's fix 1: "the brief says the whole repo ... run the
    # orphan/superseded check over tracked code and docs too: no imports, calls or citations means
    # orphan, with the grep shown"). Covers every tracked .py/.sh file except attic/ (already handled
    # per-child above). A hit anywhere in the repo's tracked text -- an import, a run command in a doc,
    # a NUMBERS.md citation -- counts as "referenced"; only a true zero-hit file is an orphan. ----
    code_files = sorted(f for f in git_tracked_files()
                         if (f.endswith(".py") or f.endswith(".sh")) and not f.startswith("attic/"))
    print(f"[CLEANUP-INV] checking {len(code_files)} tracked .py/.sh files for orphan status "
          f"(git grep for the module/file name, excluding itself)...", flush=True)
    n_code_checked, n_code_orphan = 0, 0
    for f in code_files:
        n_code_checked += 1
        base = os.path.basename(f)
        needle = base[:-3] if f.endswith(".py") else base   # .py: bare module name; .sh: full filename
        hits = grep_whole_repo(needle, exclude_path=f)
        if not hits:
            n_code_orphan += 1
            add(f, "orphan",
                f"`git grep -l -F \"{needle}\"` (excluding itself) returns no tracked file that "
                f"imports, runs, or otherwise mentions it -- not an input to, nor cited by, anything "
                f"else in the repo's own tracked text.")
    print(f"[CLEANUP-INV] tracked code orphan check: {n_code_checked} files checked, "
          f"{n_code_orphan} with zero references found.", flush=True)

    # ---- docs/prompts/*.md briefs: round-5c (Checker's fix 1 on top of round-5's fix 2) -- every
    # brief except three hard exclusions (BUILDER_HANDOFF.md and CODE_CHECKER_ROLE.md are role
    # handoffs, REPO_CLEANUP.md is this very task's own live brief) is LISTED, same as every other
    # candidate -- being cited, or itself citing/protecting another candidate, never hides a row, it
    # only annotates it via the cited_by column, same as everywhere else. But this script has no
    # reliable way to tell "closed" work from "parked" or "live" work from text alone, so defaulting
    # every one of these to reason "stale doc" (closed work, per the brief's own definition) was
    # overconfident -- the Checker named two it knows are still live (S2 is parked, not closed;
    # REVERTER_MODEL is the parent of every live S-item). Those two get reason "live -- not stale".
    # Every other brief here gets reason "stale doc" still, but with its evidence text explicitly
    # flagging "status: planner to confirm" rather than asserting closure this script cannot verify.
    # Run last so DOCS_USED_AS_CITATION_SOURCE is fully populated from every add() call above first.
    KNOWN_LIVE_BRIEFS = {
        "HL_MODEL1_S2_TREES.md": "S2 is parked, not closed (Checker's round-5c ruling).",
        "HL_MODEL1_REVERTER_MODEL.md": "the parent brief of every live S-item, Part A "
                                         "(Checker's round-5c ruling).",
    }
    for fn in sorted(os.listdir(prompts_dir)):
        if not fn.endswith(".md") or fn in ("BUILDER_HANDOFF.md", "REPO_CLEANUP.md",
                                             "CODE_CHECKER_ROLE.md"):
            continue
        rel = os.path.join("docs", "prompts", fn)
        used_as_source = rel in DOCS_USED_AS_CITATION_SOURCE
        source_note = (" This doc is itself used above to justify protecting >=1 other candidate, "
                        "so it is evidently still live despite being listed here." if used_as_source
                        else "")
        if fn in KNOWN_LIVE_BRIEFS:
            add(rel, "live -- not stale",
                f"a docs/prompts/*.md brief, checked for citation the same way every other candidate "
                f"is. NOT stale: {KNOWN_LIVE_BRIEFS[fn]}{source_note}")
        else:
            add(rel, "stale doc",
                f"a docs/prompts/*.md brief, checked for citation the same way every other candidate "
                f"is. status: planner to confirm -- this script has no reliable way to tell closed "
                f"work from parked/live work by text alone, so 'stale doc' here is a bucket for "
                f"'not one of the two the planner already confirmed are live', not a confirmed "
                f"closure.{source_note}")

    # ---- Large tracked files (>10MB), required by the brief regardless of reason ----
    large_tracked = []
    for p in sorted(git_tracked_files()):
        full = os.path.join(ROOT, p)
        if os.path.isfile(full):
            sz = os.path.getsize(full)
            if sz > 10 * 1024 * 1024:
                large_tracked.append((p, sz))
    print(f"[CLEANUP-INV] {len(large_tracked)} tracked files over 10MB found.", flush=True)

    # ---- Summary ----
    by_reason = {}
    for r in rows:
        by_reason.setdefault(r["reason"], [0, 0])
        by_reason[r["reason"]][0] += 1
        by_reason[r["reason"]][1] += r["size"]
    # Checker's fix 2 (precise accounting): sum the real `lost_size` field, not a substring match on
    # the risk text (which now also describes recoverable/mixed rows).
    untracked_lost_total = sum(r.get("lost_size", 0) for r in rows)
    # Checker's fix 6: most of the lost-for-good rows are 0-byte launch logs; split that from the
    # real data (the two pilot-dir untracked parts) so the size isn't read as spread evenly.
    ZERO_BYTE_THRESHOLD = 1024   # 1KB -- anything under this is a near-empty marker log, not data
    zero_ish = [(r["path"], r.get("lost_size", 0)) for r in rows
                if 0 < r.get("lost_size", 0) <= ZERO_BYTE_THRESHOLD]
    real_data = [(r["path"], r.get("lost_size", 0)) for r in rows
                 if r.get("lost_size", 0) > ZERO_BYTE_THRESHOLD]
    zero_ish_total = sum(s for _, s in zero_ish)
    real_data_total = sum(s for _, s in real_data)
    print("[CLEANUP-INV] === SUMMARY ===", flush=True)
    print(f"[CLEANUP-INV]   total candidates listed: {len(rows)}", flush=True)
    for reason, (cnt, sz) in sorted(by_reason.items()):
        print(f"[CLEANUP-INV]   {reason}: {cnt} candidate(s), {human(sz)}", flush=True)
    lost_rows = [r for r in rows if r.get("lost_size", 0) > 0]
    s3_yes = sum(1 for r in lost_rows if r.get("s3") and r["s3"][0] == "yes")
    s3_no = sum(1 for r in lost_rows if r.get("s3") and r["s3"][0] == "no")
    s3_nc = len(lost_rows) - s3_yes - s3_no
    print(f"[CLEANUP-INV]   untracked-data (lost-for-good) total: {human(untracked_lost_total)} "
          f"({len(zero_ish)+len(real_data)} rows); of which {human(real_data_total)} is real data "
          f"({len(real_data)} rows over {ZERO_BYTE_THRESHOLD}B) and {human(zero_ish_total)} is "
          f"near-empty launch-log markers ({len(zero_ish)} rows, {ZERO_BYTE_THRESHOLD}B or under each). "
          f"S3 checked for all {len(lost_rows)}: {s3_yes} found in S3, {s3_no} not in S3, "
          f"{s3_nc} not checked (aws failure).", flush=True)
    for p, s in real_data:
        print(f"[CLEANUP-INV]     real-data row: {p} | {human(s)}", flush=True)
    print(f"[CLEANUP-INV]   large tracked files (>10MB): {len(large_tracked)}, "
          f"{human(sum(s for _, s in large_tracked))}", flush=True)
    print(f"[CLEANUP-INV]   cited (annotated, NOT excluded): {len(PROTECTED_LOG)} candidates",
          flush=True)
    for path, doc, line_no, tok, line_text in PROTECTED_LOG:
        print(f"[CLEANUP-INV]     cited: {path} <- token \"{tok}\" in {doc}:{line_no}: "
              f"{line_text[:160]}", flush=True)

    # ---- Write docs/CLEANUP_INVENTORY.md ----
    out = []

    def w(line=""):
        out.append(line)

    w("# Cleanup inventory (Step 1 -- no deletion)")
    w()
    w(f"Generated by `scripts/cleanup_inventory.py` (sha256 `{sha}`), "
      f"`research/dataset/logs/cleanup_inventory.log`. Per the brief "
      f"(`docs/prompts/REPO_CLEANUP.md`): deletes nothing. Every size, git-status and commit figure "
      f"below is printed by this script, reading `git ls-files`/`git status`/`git log` and the "
      f"filesystem directly -- nothing hand-typed. Citation check (planner's round-5 ruling, "
      f"overriding the brief's own 'never list a cited receipt' clause for known bulk items): a "
      f"citation no longer hides a row. Every candidate below is listed regardless of whether it is "
      f"mentioned anywhere; a mention only adds a `cited by` note (`doc:line`) to that row so the "
      f"user can see the citation and still decide. A citation is a WHOLE TOKEN (a run of "
      f"`[A-Za-z0-9_./-]` -- `.` and `/` stay inside the token, so e.g. `master_funding.log` and "
      f"`master_funding_check.log` can never match each other) found in NUMBERS.md or any `.md` file "
      f"directly under `docs/` (the decisions log, the planner's handoff, `docs/STATE.md`, "
      f"`docs/VM_HANDOFF.md`, `docs/DATASET_DICTIONARY.md`, `docs/CLOUD_DEPLOY.md`, "
      f"`docs/STRATEGY_SUMMARY.md`, etc. -- note `docs/VM_HANDOFF.md` is a stale doc per the planner, "
      f"so a `cited by docs/VM_HANDOFF.md:N` note is weaker evidence than a NUMBERS.md or decisions-"
      f"log citation, and the user should weigh it accordingly) or any `docs/prompts/*.md` brief, "
      f"matching the row's path either (1) exactly, or as a suffix landing on a `/` boundary, (2) for "
      f"a FILE row, its bare basename exactly, (3) a real glob (`*` and `/` together) against the "
      f"full path, or (4) for a DIRECTORY row, a citation of a file nested inside it. Every citation "
      f"hit is logged with its document, line number, the exact matched token, and the line text -- "
      f"see 'Citation detail' below. `CLAUDE.md`, `docs/prompts/BUILDER_HANDOFF.md` (a role handoff), "
      f"`research/datasets/` (the v1 dataset and its manifest), `.venv/` (the project's own "
      f"virtualenv -- out of every list and every total, per the planner's updated brief), and "
      f"`research/dataset/logs/master_manifest_v1.log` (the v1 freeze's own provenance receipt, to be "
      f"added to git in Step 2) are excluded unconditionally, never walked -- these are the only hard "
      f"exclusions; attic/*, research/exit_study and research/live_archive are listed as ordinary "
      f"candidates below, cited or not. Every untracked-data row also gets a real, read-only `aws s3 "
      f"ls --recursive s3://{S3_BUCKET}/` check (one call, cached for all rows) in the 'in S3' "
      f"column -- `yes (<matched key>)`, `no (not at the same path)`, or `not checked` if the command "
      f"itself failed. The match is EXACT repo-relative-path-to-S3-key only (Checker's round-5c fix "
      f"2): a copy stored under a different prefix in the bucket reads as `no`, not as a confirmed "
      f"absence from S3 altogether.")
    w()
    w("## Candidates")
    w()
    w("| path | size | git status | last commit | reason | risk | in S3 | cited by |")
    w("|---|---|---|---|---|---|---|---|")
    for r in rows:
        commit = r["commit"] or "n/a"
        cited = f"`{r['cited_by']}`" if r.get("cited_by") else "-"
        s3 = r.get("s3")
        if s3 is None:
            s3_cell = "-"
        elif s3[0] == "yes":
            s3_cell = f"yes (`{s3[1]}`)"
        elif s3[0] == "no":
            s3_cell = "no (not at the same path)"
        else:
            s3_cell = "not checked"
        w(f"| `{r['path']}` | {human(r['size'])} | {r['status']} | {commit} | {r['reason']} | "
          f"{r['risk'] or '-'} | {s3_cell} | {cited} |")
    w()
    w("Evidence for each row (the grep/check that produced its reason):")
    w()
    for r in rows:
        w(f"- **`{r['path']}`**: {r['evidence']}")
    w()
    w("## Large tracked files (>10MB) -- listed regardless of reason, per the brief")
    w()
    w("| path | size | last commit |")
    w("|---|---|---|")
    for p, sz in large_tracked:
        commit = git_last_commit(p) or "n/a"
        w(f"| `{p}` | {human(sz)} | {commit} |")
    w()
    w("## .gitignore candidates")
    w()
    w("`.gitignore` already covers `__pycache__` directories, `.venv/`, `research/datasets/`, "
      "`research/exit_study/`, `attic/okx_data/`, `attic/vm_final/`, `.DS_Store`. Checker's fix 8: "
      "if any untracked-and-not-ignored candidate above is KEPT (not deleted) after Step 2's "
      "approval, it should go into `.gitignore` rather than stay as a permanent `??` in `git status` "
      "-- that applies to `research/live_archive/` and `research/hyperliquid/logs/build5_pilot/` + "
      "`build7_oipilot/`'s untracked (`.parquet`) files specifically, since those are the untracked, "
      "not-ignored rows above with real data (not 0-byte logs). This is a recommendation for "
      "whatever the user decides to KEEP, not an instruction to add it now.")
    w()
    w("## Citation detail (for rows marked `cited by` above -- none of this excludes a row)")
    w()
    w(f"{len(PROTECTED_LOG)} citation hit(s) were found among the candidates above (see each row's "
      f"`cited by` column). Every hit is shown with exactly where it was found, so the user can judge "
      f"the citation's weight (a NUMBERS.md or decisions-log receipt vs. a mention in a stale doc "
      f"like `docs/VM_HANDOFF.md`):")
    w()
    w("| path | matched token | cited by | line | text |")
    w("|---|---|---|---|---|")
    for path, doc, line_no, tok, line_text in PROTECTED_LOG:
        text_short = (line_text[:140] + "...") if len(line_text) > 140 else line_text
        text_short = text_short.replace("|", "\\|")
        tok_short = tok.replace("|", "\\|")
        w(f"| `{path}` | `{tok_short}` | `{doc}` | {line_no} | {text_short} |")
    w()
    w("## Summary")
    w()
    w("| reason | candidates | total size |")
    w("|---|---|---|")
    for reason, (cnt, sz) in sorted(by_reason.items()):
        w(f"| {reason} | {cnt} | {human(sz)} |")
    w()
    w(f"**Untracked-data (lost-for-good) total: {human(untracked_lost_total)}** across "
      f"{len(zero_ish)+len(real_data)} rows -- every one of these rows was checked against S3 "
      f"(see each row's 'in S3' column above): {s3_yes} found in S3, {s3_no} not in S3, {s3_nc} not "
      f"checked (aws failure). 'Lost for good' means no identical copy was found in git history OR "
      f"S3, per row -- this is no longer a lower bound. Split by size, since most rows are near-empty "
      f"launch-log markers, not real data:")
    w()
    w(f"- **Real data** ({len(real_data)} rows, over {ZERO_BYTE_THRESHOLD}B each): "
      f"**{human(real_data_total)}** -- " + ", ".join(f"`{p}` ({human(s)})" for p, s in real_data))
    w(f"- **Near-empty launch-log markers** ({len(zero_ish)} rows, {ZERO_BYTE_THRESHOLD}B or under "
      f"each): **{human(zero_ish_total)}** total, individually trivial.")
    w()
    w(f"Large tracked files (>10MB): {len(large_tracked)}, {human(sum(s for _, s in large_tracked))} "
      f"total.")
    w()
    w("## Scope note")
    w()
    ud_data_cite = is_cited("user_data/data")
    ud_norm_cite = is_cited("user_data/normalized")
    w(f"This inventory covers the whole repo, per the brief: known bulk directories (caches, archives, "
      f"retired experiment scratch), files matching one-off launch/probe naming patterns across every "
      f"`research/**/logs/` directory, generated build-pilot output directories, `docs/prompts/*.md` "
      f"briefs not cited anywhere, loose top-level files with zero references in the repo's own text, "
      f"and -- per the planner's fix, since code is the main bloat -- every one of the "
      f"{n_code_checked} tracked `.py`/`.sh` files outside `attic/`, each checked individually by "
      f"`git grep` for its module/file name; {n_code_orphan} had zero references anywhere in the "
      f"repo's own tracked text and are listed as orphan candidates above. `user_data/data` and "
      f"`user_data/normalized` were checked the same way as everything else and came back cited "
      f"(by `{ud_data_cite}` and `{ud_norm_cite}` respectively, as live data-location references) -- "
      f"not listed as candidates.")

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(out) + "\n")
    print(f"[CLEANUP-INV] wrote {OUT_MD}  [{time.time()-t0:.0f}s]", flush=True)
    print(f"[CLEANUP-INV] ALL DONE  [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
