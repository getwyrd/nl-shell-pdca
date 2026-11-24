"""The docs checks (scripts/docs_checks.py) that enforce ADR-0001's immutability rule.

ADR-0001 (docs/design/adr/0001-record-architecture-decisions.md:22-23, :30-31) says an
Accepted ADR is never edited and that a docs CI check enforces it; docs/design/README.md:18-21
and docs/design/proposals/README.md:10-11 say the same for stable specs and accepted
proposals. Each test builds a throwaway git repo, makes a base and a head commit, and runs
the check as a subprocess. The script is never imported, so a missing script fails each
test instead of breaking collection.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "docs_checks.py"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "docs-check test",
    "GIT_AUTHOR_EMAIL": "docs-check@example.invalid",
    "GIT_COMMITTER_NAME": "docs-check test",
    "GIT_COMMITTER_EMAIL": "docs-check@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
}

ADR = "docs/design/adr"
PROP = "docs/design/proposals"
SPEC = "docs/design/specs"


def adr(status: str, body: str = "We decide X.") -> str:
    return (
        f"---\ncreated: 14.10.2026 19:22\ntype: adr\nstatus: {status}\ntags:\n  - adr\n---\n"
        f"# 0042. A decision\n\n## Context\n\nSome context.\n\n## Decision\n\n{body}\n"
    )


def proposal(status: str, body: str = "The plan.") -> str:
    return (
        f"---\ncreated: 14.10.2026 19:22\ntype: proposal\nstatus: {status}\nauthor:\n---\n"
        f"# 0001. A proposal\n\n{body}\n"
    )


def spec(status: str, body: str = "The format MUST be JSON.") -> str:
    return (
        f"---\ncreated: 14.10.2026 19:22\ntype: spec\nstatus: {status}\nversion: v1\n---\n"
        f"# Policy gate v1\n\n{body}\n"
    )


class Repo:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q")

    def git(self, *args: str) -> str:
        env = {**os.environ, **GIT_ENV}
        result = subprocess.run(
            [
                "git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main",
                "-c", "core.autocrlf=false", *args,
            ],
            cwd=self.root, env=env, capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()

    def write(self, files: dict[str, str | bytes | None]) -> None:
        for rel, text in files.items():
            path = self.root / rel
            if text is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(text, bytes):
                path.write_bytes(text)
            else:
                path.write_text(text, encoding="utf-8")

    def commit(self, files: dict[str, str | bytes | None] | None = None) -> str:
        if files:
            self.write(files)
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "change")
        return self.git("rev-parse", "HEAD")

    def move(self, old: str, new: str) -> None:
        (self.root / new).parent.mkdir(parents=True, exist_ok=True)
        self.git("mv", old, new)


def run_check(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd, env={**os.environ, **GIT_ENV}, capture_output=True, text=True,
    )


def immutability(repo: Repo, base: str, head: str) -> subprocess.CompletedProcess:
    return run_check(repo.root, "immutability", base, head)


def scenario(tmp_path, base_files, head_files, moves=()):
    repo = Repo(tmp_path / "repo")
    base = repo.commit(base_files)
    for old, new in moves:
        repo.move(old, new)
    head = repo.commit(head_files)
    return immutability(repo, base, head)


ADR_PATH = f"{ADR}/0042-a-decision.md"
PROP_ACCEPTED = f"{PROP}/accepted/0001-implementation-arc.md"
PROP_DRAFT = f"{PROP}/draft/0001-implementation-arc.md"
SPEC_PATH = f"{SPEC}/policy-gate/v1.md"


# --- (a) immutability: must fail ------------------------------------------------------

MUST_FAIL = {
    "accepted-adr-body": (
        {ADR_PATH: adr("Accepted")}, {ADR_PATH: adr("Accepted", "We decide Y.")},
    ),
    "superseded-adr-body": (
        {ADR_PATH: adr("Superseded by ADR-0013")},
        {ADR_PATH: adr("Superseded by ADR-0013", "We decide Y.")},
    ),
    "superseded-adr-status": (
        {ADR_PATH: adr("Superseded by ADR-0013")}, {ADR_PATH: adr("Superseded by ADR-0021")},
    ),
    "superseded-adr-back-to-proposed": (
        {ADR_PATH: adr("Superseded by ADR-0013")}, {ADR_PATH: adr("Proposed")},
    ),
    "accepted-adr-to-implemented": (
        {ADR_PATH: adr("Accepted")}, {ADR_PATH: adr("Implemented")},
    ),
    "accepted-adr-to-proposed": (
        {ADR_PATH: adr("Accepted")}, {ADR_PATH: adr("Proposed")},
    ),
    "accepted-adr-status-and-body": (
        {ADR_PATH: adr("Accepted")},
        {ADR_PATH: adr("Superseded by ADR-0050", "We decide Y.")},
    ),
    "accepted-adr-deleted": ({ADR_PATH: adr("Accepted")}, {ADR_PATH: None}),
    "accepted-proposal-body": (
        {PROP_ACCEPTED: proposal("accepted")},
        {PROP_ACCEPTED: proposal("accepted", "Another plan.")},
    ),
    "accepted-proposal-to-superseded": (
        {PROP_ACCEPTED: proposal("accepted")}, {PROP_ACCEPTED: proposal("superseded")},
    ),
    "implemented-proposal-body": (
        {PROP_ACCEPTED: proposal("implemented")},
        {PROP_ACCEPTED: proposal("implemented", "Another plan.")},
    ),
    "implemented-proposal-status": (
        {PROP_ACCEPTED: proposal("implemented")}, {PROP_ACCEPTED: proposal("withdrawn")},
    ),
    "withdrawn-proposal-body": (
        {PROP_ACCEPTED: proposal("withdrawn")},
        {PROP_ACCEPTED: proposal("withdrawn", "Another plan.")},
    ),
    "stable-spec-body": (
        {SPEC_PATH: spec("stable")}, {SPEC_PATH: spec("stable", "The format MUST be YAML.")},
    ),
    "stable-spec-to-draft": ({SPEC_PATH: spec("stable")}, {SPEC_PATH: spec("draft")}),
    "superseded-spec-body": (
        {SPEC_PATH: spec("superseded")},
        {SPEC_PATH: spec("superseded", "The format MUST be YAML.")},
    ),
    "withdrawn-spec-body": (
        {SPEC_PATH: spec("withdrawn")},
        {SPEC_PATH: spec("withdrawn", "The format MUST be YAML.")},
    ),
    "withdrawn-spec-status": (
        {SPEC_PATH: spec("withdrawn")}, {SPEC_PATH: spec("stable")},
    ),
}


@pytest.mark.parametrize("base_files,head_files", MUST_FAIL.values(), ids=MUST_FAIL.keys())
def test_frozen_record_change_fails(tmp_path, base_files, head_files):
    result = scenario(tmp_path, base_files, head_files)
    out = result.stdout + result.stderr
    assert result.returncode == 1, out
    (path,) = base_files
    assert path in result.stdout, out
    assert "supersede" in result.stdout, out


def test_renaming_an_accepted_adr_fails_at_its_old_path(tmp_path):
    new = f"{ADR}/0042-renamed.md"
    result = scenario(
        tmp_path, {ADR_PATH: adr("Accepted")}, None, moves=[(ADR_PATH, new)]
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert ADR_PATH in result.stdout


def test_moving_an_accepted_proposal_fails(tmp_path):
    other = f"{PROP}/draft/0001-implementation-arc.md"
    result = scenario(
        tmp_path, {PROP_ACCEPTED: proposal("accepted")}, None,
        moves=[(PROP_ACCEPTED, other)],
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert PROP_ACCEPTED in result.stdout


def test_every_offending_path_is_reported(tmp_path):
    other = f"{ADR}/0043-another.md"
    result = scenario(
        tmp_path,
        {ADR_PATH: adr("Accepted"), other: adr("Accepted")},
        {ADR_PATH: adr("Accepted", "Y."), other: adr("Accepted", "Z.")},
    )
    assert result.returncode == 1
    assert ADR_PATH in result.stdout and other in result.stdout


# --- (a) immutability: must pass ------------------------------------------------------

MUST_PASS = {
    "proposed-adr-body": (
        {ADR_PATH: adr("Proposed")}, {ADR_PATH: adr("Proposed", "We decide Y.")},
    ),
    "partly-superseded-proposed-adr-body": (
        {ADR_PATH: adr("Proposed (backend order and VRAM budget superseded by ADR-0019)")},
        {ADR_PATH: adr(
            "Proposed (backend order and VRAM budget superseded by ADR-0019)", "Y."
        )},
    ),
    "adr-proposed-to-accepted": (
        {ADR_PATH: adr("Proposed")}, {ADR_PATH: adr("Accepted")},
    ),
    "adr-proposed-to-accepted-with-edit": (
        {ADR_PATH: adr("Proposed")}, {ADR_PATH: adr("Accepted", "We decide Y.")},
    ),
    "accepted-adr-to-superseded": (
        {ADR_PATH: adr("Accepted")}, {ADR_PATH: adr("Superseded by ADR-0050")},
    ),
    "accepted-adr-to-superseded-with-suffix": (
        {ADR_PATH: adr("Accepted")},
        {ADR_PATH: adr("Superseded by ADR-0050 and ADR-0051 (2026-11-01)")},
    ),
    "accepted-adr-to-superseded-lowercase": (
        {ADR_PATH: adr("accepted")}, {ADR_PATH: adr("superseded by adr-0050")},
    ),
    "accepted-proposal-to-implemented": (
        {PROP_ACCEPTED: proposal("accepted")}, {PROP_ACCEPTED: proposal("implemented")},
    ),
    "accepted-proposal-to-withdrawn": (
        {PROP_ACCEPTED: proposal("accepted")}, {PROP_ACCEPTED: proposal("withdrawn")},
    ),
    "draft-proposal-body": (
        {PROP_DRAFT: proposal("draft")}, {PROP_DRAFT: proposal("draft", "Another plan.")},
    ),
    "draft-spec-body": (
        {SPEC_PATH: spec("draft")}, {SPEC_PATH: spec("draft", "The format MUST be YAML.")},
    ),
    "spec-draft-to-stable": ({SPEC_PATH: spec("draft")}, {SPEC_PATH: spec("stable")}),
    "stable-spec-to-superseded": (
        {SPEC_PATH: spec("stable")}, {SPEC_PATH: spec("superseded")},
    ),
    "stable-spec-to-withdrawn": (
        {SPEC_PATH: spec("stable")}, {SPEC_PATH: spec("withdrawn")},
    ),
    "new-spec-version": (
        {SPEC_PATH: spec("stable")},
        {f"{SPEC}/policy-gate/v2.md": spec("draft")},
    ),
    "new-adr-and-proposal": (
        {ADR_PATH: adr("Accepted")},
        {f"{ADR}/0043-new.md": adr("Proposed"), f"{PROP}/draft/0002-new.md": proposal("draft")},
    ),
    "indexes-edited": (
        {
            f"{ADR}/README.md": "# ADRs\n",
            f"{PROP}/README.md": "# Proposals\n",
            f"{SPEC}/README.md": "# Specs\n",
            ADR_PATH: adr("Accepted"),
        },
        {
            f"{ADR}/README.md": "# ADRs\n\nEdited.\n",
            f"{PROP}/README.md": "# Proposals\n\nEdited.\n",
            f"{SPEC}/README.md": "# Specs\n\nEdited.\n",
        },
    ),
    "no-frontmatter-status": (
        {ADR_PATH: "# 0042. No frontmatter\n\nBody.\n"},
        {ADR_PATH: "# 0042. No frontmatter\n\nEdited.\n"},
    ),
    "other-docs-edited": (
        {"docs/design/architecture/01-intro.md": "---\nstatus: living\n---\n# Intro\n"},
        {"docs/design/architecture/01-intro.md": "---\nstatus: living\n---\n# Intro 2\n"},
    ),
}


@pytest.mark.parametrize("base_files,head_files", MUST_PASS.values(), ids=MUST_PASS.keys())
def test_allowed_change_passes(tmp_path, base_files, head_files):
    result = scenario(tmp_path, base_files, head_files)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_ratifying_proposal_moves_from_draft_to_accepted(tmp_path):
    """The #6 ratification step: draft/ -> accepted/ while the status becomes accepted."""
    repo = Repo(tmp_path / "repo")
    base = repo.commit({PROP_DRAFT: proposal("draft")})
    repo.move(PROP_DRAFT, PROP_ACCEPTED)
    head = repo.commit({PROP_ACCEPTED: proposal("accepted")})
    result = immutability(repo, base, head)
    assert result.returncode == 0, result.stdout + result.stderr


def test_frozen_state_comes_from_the_base_not_the_head(tmp_path):
    """Accepting an ADR in a PR does not freeze it for that PR; accepting it on main does."""
    repo = Repo(tmp_path / "repo")
    base = repo.commit({ADR_PATH: adr("Proposed")})
    accepted = repo.commit({ADR_PATH: adr("Accepted")})
    edited = repo.commit({ADR_PATH: adr("Accepted", "We decide Y.")})
    assert immutability(repo, base, edited).returncode == 0
    result = immutability(repo, accepted, edited)
    assert result.returncode == 1
    assert ADR_PATH in result.stdout


def diverged(tmp_path, main_files, pr_files):
    """Branch a PR off a Proposed ADR, then commit `main_files` on main and `pr_files` on
    the PR branch. Returns (repo, main tip, PR head)."""
    repo = Repo(tmp_path / "repo")
    repo.commit({ADR_PATH: adr("Proposed"), "docs/other.md": "# Other\n"})
    repo.git("branch", "pr")
    main_tip = repo.commit(main_files)
    repo.git("checkout", "-q", "pr")
    pr_head = repo.commit(pr_files)
    return repo, main_tip, pr_head


def test_adr_accepted_on_main_after_the_pr_branched_is_frozen(tmp_path):
    """Merge-base still says Proposed, but the base tip has it Accepted: the edit fails."""
    repo, main_tip, pr_head = diverged(
        tmp_path,
        {ADR_PATH: adr("Accepted")},
        {ADR_PATH: adr("Proposed", "We decide Y.")},
    )
    result = immutability(repo, main_tip, pr_head)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ADR_PATH in result.stdout
    assert "base tip" in result.stdout


def test_diverged_pr_editing_a_still_proposed_adr_passes(tmp_path):
    repo, main_tip, pr_head = diverged(
        tmp_path,
        {"docs/other.md": "# Other, edited on main\n"},
        {ADR_PATH: adr("Proposed", "We decide Y.")},
    )
    result = immutability(repo, main_tip, pr_head)
    assert result.returncode == 0, result.stdout + result.stderr


def test_diverged_pr_not_touching_the_accepted_adr_passes(tmp_path):
    repo, main_tip, pr_head = diverged(
        tmp_path,
        {ADR_PATH: adr("Accepted")},
        {"docs/other.md": "# Other, edited on the PR\n"},
    )
    result = immutability(repo, main_tip, pr_head)
    assert result.returncode == 0, result.stdout + result.stderr


def test_crlf_rewrite_of_an_accepted_adr_fails(tmp_path):
    """Comparison is byte-exact: LF -> CRLF is an edit, even though the text is the same."""
    lf = adr("Accepted").encode()
    result = scenario(tmp_path, {ADR_PATH: lf}, {ADR_PATH: lf.replace(b"\n", b"\r\n")})
    assert result.returncode == 1, result.stdout + result.stderr
    assert ADR_PATH in result.stdout


def test_crlf_on_an_allowed_status_line_change_fails(tmp_path):
    base = adr("Accepted").encode()
    head = adr("Superseded by ADR-0050").encode().replace(
        b"status: Superseded by ADR-0050\n", b"status: Superseded by ADR-0050\r\n"
    )
    result = scenario(tmp_path, {ADR_PATH: base}, {ADR_PATH: head})
    assert result.returncode == 1, result.stdout + result.stderr
    assert ADR_PATH in result.stdout


def test_crlf_accepted_adr_status_only_change_passes(tmp_path):
    """A record stored with CRLF may still take its allowed status-line change."""
    base = adr("Accepted").encode().replace(b"\n", b"\r\n")
    head = adr("Superseded by ADR-0050").encode().replace(b"\n", b"\r\n")
    result = scenario(tmp_path, {ADR_PATH: base}, {ADR_PATH: head})
    assert result.returncode == 0, result.stdout + result.stderr


# --- (b) links ------------------------------------------------------------------------


def links_repo(tmp_path, files):
    repo = Repo(tmp_path / "repo")
    repo.commit({"docs/target.md": "# Target\n", "docs/sub/other.png": "png", **files})
    return run_check(repo.root, "links")


@pytest.mark.parametrize(
    "line,link",
    [
        ("See [the target](missing.md).", "missing.md"),
        ("See [the target](missing.md#section).", "missing.md#section"),
        ("An image: ![alt](sub/missing.png)", "sub/missing.png"),
        ("Up a level: [x](../nope/target.md)", "../nope/target.md"),
        ("[ref]: missing-ref.md", "missing-ref.md"),
        ("[ref]: missing-ref.md#frag", "missing-ref.md#frag"),
        ("Two: [ok](target.md) and [bad](gone.md)", "gone.md"),
        ("Out of the repo: [x](../../outside.md)", "../../outside.md"),
    ],
)
def test_broken_relative_link_fails(tmp_path, line, link):
    result = links_repo(tmp_path, {"docs/page.md": f"# Page\n\n{line}\n"})
    assert result.returncode == 1, result.stdout + result.stderr
    assert "docs/page.md" in result.stdout
    assert link in result.stdout


def test_link_to_an_untracked_file_fails(tmp_path):
    repo = Repo(tmp_path / "repo")
    repo.commit({"docs/page.md": "[x](untracked.md)\n"})
    (repo.root / "docs" / "untracked.md").write_text("# not tracked\n")
    result = run_check(repo.root, "links")
    assert result.returncode == 1
    assert "untracked.md" in result.stdout


def test_valid_and_ignored_links_pass(tmp_path):
    page = """# Page

[file](target.md), [with fragment](target.md#target), [dir](sub/), [dir2](sub),
![image](sub/other.png), [up](../README.md), [self](page.md), [angle](<target.md>)
[web](https://example.com/missing.md), [mail](mailto:someone@example.com),
[ftp](ftp://example.com/x.md), [anchor](#page), [proto](//example.com/x.md)
Inline code `[x](missing-inline.md)` and ``[y](missing-double.md)`` are ignored.

[ref]: target.md
[web-ref]: https://example.com/gone.md
[frag-ref]: #page

```
[fenced](missing-fenced.md)
[fenced-ref]: missing-fenced-ref.md
```

~~~markdown
[tilde](missing-tilde.md)
~~~

After the fences: [ok](target.md).
"""
    result = links_repo(tmp_path, {"docs/page.md": page, "README.md": "# Root\n"})
    assert result.returncode == 0, result.stdout + result.stderr


def test_link_after_a_closed_fence_is_checked(tmp_path):
    page = "```\n[fenced](missing-a.md)\n```\n\n[after](missing-b.md)\n"
    result = links_repo(tmp_path, {"docs/page.md": page})
    assert result.returncode == 1
    assert "missing-b.md" in result.stdout
    assert "missing-a.md" not in result.stdout


# Markdown that holds no broken relative link, though a naive scanner would find one.
NOT_A_BROKEN_LINK = {
    "footnote-definition": "A claim.[^1]\n\n[^1]: See the ADR index for details.\n",
    "footnote-definition-with-path-like-text": "Hi.[^note]\n\n[^note]: missing.md\n",
    "balanced-parens-in-destination": "See [v1](file(v1).md) and [v1 again](file(v1).md#x).\n",
    "escaped-parens-in-destination": "See [v1](file\\(v1\\).md).\n",
    "code-span-across-lines": "Use `[x](missing-a.md)\nand [y](missing-b.md)` here.\n",
    "double-backtick-span-across-lines": "Use ``a ` [x](missing.md)\n`` here.\n",
    "indented-code-block": "Example:\n\n    [x](missing.md)\n    [ref]: missing-ref.md\n\nDone.\n",
    "tab-indented-code-block": "Example:\n\n\t[x](missing.md)\n",
    "html-comment": "<!-- [x](missing.md) -->\nText.\n",
    "html-comment-across-lines": "<!--\nTODO: [x](missing.md)\n[ref]: missing-ref.md\n-->\n",
    "html-comment-inline": "Text <!-- [x](missing.md) --> more [ok](target.md).\n",
}


@pytest.mark.parametrize("page", NOT_A_BROKEN_LINK.values(), ids=NOT_A_BROKEN_LINK.keys())
def test_markdown_that_is_not_a_broken_link_passes(tmp_path, page):
    result = links_repo(
        tmp_path, {"docs/page.md": f"# Page\n\n{page}", "docs/file(v1).md": "# v1\n"}
    )
    assert result.returncode == 0, result.stdout + result.stderr


# The masking above must not hide real links next to it.
STILL_A_BROKEN_LINK = {
    "balanced-parens-missing": ("See [v2](file(v2).md).\n", "file(v2).md"),
    "after-a-footnote": ("A.[^1]\n\n[^1]: Note.\n\n[ref]: gone.md\n", "gone.md"),
    "after-a-code-span-closes": ("`a\nb` then [x](gone.md)\n", "gone.md"),
    "after-an-html-comment": ("<!-- c -->\n[x](gone.md)\n", "gone.md"),
    "after-an-indented-block": ("x\n\n    code\n\n[x](gone.md)\n", "gone.md"),
    "indented-paragraph-continuation": ("Para\n    [x](gone.md)\n", "gone.md"),
    "indented-list-item-content": ("1. Item\n\n    [x](gone.md)\n", "gone.md"),
    "unclosed-backtick": ("A lone ` then [x](gone.md)\n", "gone.md"),
}


@pytest.mark.parametrize(
    "page,link", STILL_A_BROKEN_LINK.values(), ids=STILL_A_BROKEN_LINK.keys()
)
def test_broken_link_next_to_ignored_markdown_fails(tmp_path, page, link):
    result = links_repo(
        tmp_path, {"docs/page.md": f"# Page\n\n{page}", "docs/file(v1).md": "# v1\n"}
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "docs/page.md" in result.stdout
    assert f"'{link}'" in result.stdout


# --- (c) the live nl-shell tree -------------------------------------------------------


def test_live_tree_has_no_broken_links():
    """Runs against this checkout, so a broken link on main turns the suite red too.

    Uses `git ls-files` from the repo root, which also works in a worktree (.git is a file).
    """
    result = run_check(REPO_ROOT, "links")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
