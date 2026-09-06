# Engineering Decision Principles

These rules apply to implementation, repair, refactoring, and test work in this repository.

- Diagnose before changing code. Classify a failure as a product-semantic, authority-boundary, abstraction, integration, implementation, or test-instrument problem, and fix it at the owning layer.
- Prefer the smallest coherent structural change that removes the root cause across providers, models, and journeys. Reuse and simplify existing contracts before adding a new field, state, branch, abstraction, or fallback.
- Do not over-defend a local failure. Identify the one missing fact or broken invariant at the failing boundary and repair it in the component that already owns the necessary context. Do not add another model pass, Host classifier, schema, typed envelope, fallback, duplicated context, or speculative guard unless evidence shows that the smaller root-cause fix is insufficient. Prefer one explainable invariant over several overlapping protections.
- Do not solve general problems with provider-specific shortcuts, prompt keyword patches, duplicated sources of truth, silent retries, or growing exception lists. If a special case is genuinely required, state the invariant that makes it exceptional and keep it bounded and observable.
- Treat defenses as proportional to risk. Fail closed for permissions, destructive actions, identity ambiguity, and execution authority; do not add speculative guards that mask defects, block valid interaction, or make ordinary flows brittle.
- Keep responsibilities explicit: models interpret semantics; the host owns identity, durable state, permissions, execution authority, and ledger facts. Model-generated translations and narration are evidence or presentation, not new authority sources.
- Test semantic contracts and user-visible outcomes rather than incidental wording, filenames, timing, or tool order unless those details are themselves part of the contract. Cover both sides of a boundary so a fix cannot merely trade one regression for another.
- Before retaining a compatibility path or workaround, prove that a live caller still needs it. Remove superseded defenses and update the relevant tests and documentation when a structural fix replaces them.
- Optimize for code that a new maintainer can explain from its invariants. Elegance here means fewer independent rules, clear ownership, observable failure, and no loss of necessary safety—not merely fewer lines.

## Fork Git Workflow

This fork keeps `upstream/main` as the read-only upstream baseline, local `main` as the clean synchronization branch, and `origin/main` as the fork's mirror of local `main`. Product work belongs on one branch per work item: `feature/*` for features, `fix/*` for bug fixes, or the documented `docs/*`, `test/*`, `chore/*`, and `refactor/*` equivalents. Do not develop directly on `main`.

After a fresh clone, enable the repository hooks with `.\scripts\setup_git_workflow.ps1`. Use `.\scripts\sync_main.ps1` to fetch `upstream`, fast-forward local `main`, and push the synchronized main to `origin`. Use `.\scripts\new_work_branch.ps1 -Name <name> -Kind feature|fix` to create a work branch from the synchronized `main`. Full details are in [docs/git-workflow.md](docs/git-workflow.md). The hooks block direct commits on `main` and all pushes to `upstream`; they do not replace review or testing.
