# Developer documentation

Use repository documentation in this order:

1. [Roadmap](roadmap.md) records the agreed scope, decisions, and phase plan.
2. [Accepted ADRs](adr/README.md) record conventions that must not change
   silently: frames, signs, angle definitions, and normalization. A later ADR
   takes priority only for the parts it explicitly supersedes.

The [release procedure](development/release.md) describes tagging and
GitHub Releases.

The user documentation in `docs/` (Sphinx) is a separate manual written for
first-time users of the package. It does not cite ADRs, this directory, or the
repository host. `docs/getting_started/conventions.rst` restates the accepted
ADRs in user terms: update it in the same change as any ADR, and treat the ADR
as authoritative if the two disagree.

Add an ADR before implementing any new sign, axis, angle, or normalization
convention.
