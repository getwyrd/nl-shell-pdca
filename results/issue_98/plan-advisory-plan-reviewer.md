Bash was unavailable in this run (every command failed with `apply-seccomp: write /proc/self/setgroups … Permission denied`); this review used Read, Grep and Glob only.

# Plan review — docs-checks-internal-links

- NEEDS-HUMAN — **The base is wrong for scope item (3): the prerequisite has not landed.** `dependency-state.json` lists `"97": {"declared": "Depends on", "state": "PLANNED"}`, so child-1 has not been built, let alone merged. The brief still targets `eduralph/nl-shell @ main` (brief l.31). Scope (3) adds "One step in `.github/workflows/docs-checks.yml` (created by child-1) after the freeze step" (l.36). That file does not exist on the target: `.github/workflows/` contains only `require-linked-issue.yml`, `triage-new-issue.yml` and `tests.yml`. If Do starts from `main` it has nothing to add a step to, and no "freeze step" to put it after. It would either have to invent child-1's workflow, which is a hidden second change that collides with #97, or drop (3). The brief needs one of two fixes: declare `Stacks on: 97` and target child-1's branch, or hold this bundle until #97 merges. "Depends on" against a PLANNED prereq with a `main` base will strand the run.

- NEEDS-HUMAN — **The tracker record is missing from the bundle, so the problem framing and "maintainer decision 5" cannot be checked.** The sandbox has only `brief.md` and `dependency-state.json`. There is no `notes.json` and no `sources/`. The whole link rule (l.20–29) and the instruction to "judge the parser against the fixed link rule below, not against CommonMark" (l.8–11) rest on "maintainer decision 5, 2026-10-15" and "the parent cycle ran three rounds". I could not check either against a thread quote. A human should confirm that decision 5 says what l.20–30 encode, especially the deliberate gaps: unclosed `<!--` masks the rest of the file, 4-space indented code is not recognized. Those gaps define what counts as correct for every downstream Check.

- NEEDS-HUMAN — **Do is pointed at an input outside the bundle.** l.37 says to reuse `cmd_links` from `/home/eddie/nl-shell/nl-shell-pdca/results/issue_7/iteration-v3/patch.diff`, but l.3 says "Do reads ONLY this file". That is an absolute host path to another run's artifact. It is not in the bundle or in `$PDCA_TARGET`, and Do may not be able to read it in its sandbox. The parent's code was also written during the three CommonMark rounds that decision 5 ended, so "reuse what fits" invites drift back toward CommonMark behaviour. Either copy the relevant excerpt into the bundle or drop the pointer. As written it is an unverifiable dependency.

- NEEDS-HUMAN — **Live-tree claims could only be partly checked.** Without Bash I could not run `git ls-files` to confirm "53 tracked `.md` files, 60 relative links, 0 broken" (l.17). What I could check holds:
  - `docs/design/adr/README.md:26` has `[0001](0001-record-architecture-decisions.md)`, so the repro target exists.
  - `tests/conftest.py:52-56` does set a temp `HOME`, so the git-identity requirement is justified.
  - `.github/workflows/tests.yml:23` runs plain `python -m pytest`, so (c) will run there as the brief says.
  - A grep for `<!--`, indented fences and reference definitions in `*.md` matched only `docs/design/templates/{adr,architecture,spec}.md`, which fits l.30.

  Criterion (c) is a hard pass/fail on the live tree, so the "0 broken" count should be re-verified with a command before Do starts.

- NEEDS-HUMAN — **Criterion (b)'s "cases for each rule step" is open-ended.** l.16 asks for "cases for each rule step, and for the round-3 cases". The round-3 cases (l.29) are listed concretely, but "each rule step" has no list. That leaves the Check reviewer to argue over coverage, and it reopens the edge-case chase l.8–11 is meant to close. A fix would be to list the minimum must-fail and must-pass cases per step, e.g. step 3 escaped backtick, step 3 unmatched run, step 4 balanced parens, step 4 `[^1]:` footnote skipped, the image link and the `#fragment`-stripped link. Then the success criterion becomes a checklist instead of a judgment call.

On the rest: I tried to fault the falsifiability design (logic in `scripts/`, which C4 reverts; the test runs the script as a subprocess, so the red leg is a clean failure and not a collection error) and the out-of-scope list. I could not fault either.

> **pdca:** Bash was unavailable to this reviewer. The vendor sandbox could not start on this host, so every Bash call it made failed before running (`apply-seccomp: write /proc/self/setgroups (nested userns is capability-restricted; caller must provide CAP_SYS_ADMIN): Permission denied`) and it ran no commands; this review was delivered without Bash.

<!-- pdca:leaf-complete -->
