# Security review (advisory) — issue 102, session terminal ownership, round 4

Attacker-reachable inputs this diff touches: command output (controlled by the text-only attacker in the threat model) going through the §6 mirror and the alternate-screen capture filter (`_AltScreen`), plus bytes typed on the real terminal and forwarded during the §6 window. The threat model treats the typed bytes as the user's own; their secrecy is a §6.1 property.

This round changes one thing in code: a `0x9b` byte that is part of a UTF-8 character is no longer read as an 8-bit CSI. It also adds one Known-gaps line. I reviewed that change against the threat model. The human accepted the drain race, the Ctrl-C-at-end race and the unfiltered mirror for v1, so I do not raise them again.

**No new finding.** What I checked:

- **UTF-8 `0x9b` is now text.** `src/nl_shell/session_terminal.py:79-97` (`_c1_csi_at`) and the check at `:143`. I ran `_AltScreen.filter` directly (`python3 -I`, using the module from `$PDCA_TARGET/src`):
  - `Û?1049h` (C3 9B) is kept in the capture and the mode stays `None`.
  - A fake `ћ?47l` (D1 9B) inside a real `ESC [?47h` does not resume capture (mode stays 47).
  - The 3-byte case (E2 80 9B) and the 4-byte case (F0 9F 98 9B) are also kept as text.
  - C2 9B (U+009B) still acts as CSI, and its C2 lead byte is not left in the capture (`b"A\xc2\x9b?1049hHID\xc2\x9b?1049lZ"` gives `b"AZ"`).
- **Sequences split across reads.** `_held_tail` / `_before` at `:100-111` and `:146-152`. I split `AÛ?1049hB` at every one of offsets 1–9, and split `A\xc2\x9b?1049hHID` at offsets 1–5. Every split gave the same result as a single read. The lead byte carried in `_before` is used correctly, so splitting the output across reads does not get around the fix.
- **Test coverage.** `tests/test_session_terminal.py:188` and `:218-225` cover the cases the sign-off asked for (`Û`, `ћ`, a 3-byte character, C2 9B, raw 9B). They also feed the filter one byte at a time, which covers the split-read case. So the attacker-reachable cases are tested, not only the friendly ones.
- **Known gap added.** The Ctrl-C-at-command-end race is now listed at `.oss-scanner/threat_model.md:226-232`, as the sign-off asked.
- **What remains, below a finding.** A raw `0x9b` with no lead byte before it is still read as CSI (`_c1_csi_at` returns True, `:96`). A terminal in UTF-8 mode usually ignores a raw `0x9b`, so `printf 'A\x9b?1049hSHOWN'` drops `SHOWN` from the capture while the user still sees it. Losing untrusted text from the capture breaks nothing in "What must hold". The opposite case only brings alt-screen text into the capture, and captured output is untrusted anyway. The sign-off asked for exactly this rule, and it says so in the docstring at `:80-82`. Low at most, and already settled.
- **Gates.** C4 (red 19 of 19 before the fix, green after) and T3 (the full suite) pass in `check-gates.json`. T2 sees the threat model updated.

<!-- pdca:leaf-complete -->
