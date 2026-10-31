# Differential security review

## Executive summary

FOCUSED review of a medium-sized addon repository, high-risk emphasis on authentication boundaries, protected creation and financial values. Baseline `24d22c3` includes PR #14. Review recommendation: **conditional on branch CI and unresolved deployment/dependency gates**. No security check was intentionally removed; no finance/contractor/company access was expanded. Findings and severity distribution are in `findings.md`.

## What changed

The branch tightens transient record access, closes effective-default validation gaps, normalizes new uploads, adds private cache policy and regression/runtime/recovery tooling. Payment caps, rounding, eligibility dates, historical rates, receipt/cancellation semantics and Morning independence are retained. Security code is isolated from visual redesign and from Morning PR #9. `git diff --stat` at the reviewed commit is the authoritative file/line count, including new files.

## Historical context and critical findings

Blame traced explicit review/create guards to `27f121a`/`dce3f27`, dispatch to the prior dispatch workflow, pricing snapshot guards to `967127e`, photo CRUD/access to `2bc2e4c` and financial dialog ACLs to `b912970`. The older guards prevented explicit writes; native default injection occurred later. These changes extend those guards rather than remove them. The monthly statement's existing creator/company/provider protections are retained. Global contractor native-project/task deny rules are retained.

The baseline used for clean reproduction was unchanged application code plus synthetic tests. Each confirmed fix has both a denied path and an allowed path in the suite. Public documentation gives source/test anchors rather than live exploitation instructions or real record identifiers.

## Test coverage analysis

187 native test methods passed locally (169 retained, 18 added). Thirteen new transaction methods target the affected boundaries; five HTTP methods cover alternate routes and direct calls. Two-session and restore checks use real commits/requests in a disposable pilot, outside transaction-mocked HttpCase. Full browser/PDF/restart checks are a separate CI requirement. Method counts are not line coverage; no numeric coverage percentage is claimed.

## Blast radius analysis

| Change | Static addon call sites excluding definition/tests | Review/validation |
|---|---:|---|
| Image validation/normalization helper | 4 | Main create/write and extra create/write; explicit/default uploads, stored metadata and existing flow tests |
| Photo effective-parent validation | 5 callers of existing editability helper | Lock/state/count and default-parent tests; normal gallery operations |
| Dispatch locking dependency | 12 call sites | Lock order left unchanged; native suite and two-session payments |
| New report controller wrapper | 1 super delegation; 2 native download dispatch calls plus routed HTTP | Retains native auth/readonly routing; provider and direct HTTP/real-PDF checks |
| Private wizard actions/rules | 3 action methods, their native form buttons and RPC | Explicit action checks plus creator/company/kind tests; legitimate actions still succeed |
| Protected default_get chain | Native ORM/form call graph is dynamic, not finitely counted | Only protected fields stripped; native forms/creation/dispatch suite retained |

Static text counts are lower bounds; inherited ORM, RPC, related-field inverses and QWeb routes are not measured by simple grep. No claim of a complete framework call graph.

## Adversarial review and regression risks

Considered arbitrary IDs/defaults/fields, inactive/reassigned jobs, forbidden finance fields, another creator/company, generic binary/download paths, raw text/image input and concurrent replay. Global rules intersect existing group grants, so they cannot be undone by a second broad group rule. Private state mutations still use server-controlled super calls. No sudo result was added to a public model method, no dynamic SQL was added, and no untrusted URL fetch was introduced.

The image change intentionally recompresses new JPEG/WebP and discards metadata/animation; orientation is preserved. Existing images are untouched. New WebP plugin registration is limited to the declared supported format rather than all Pillow plugins. Dialog privacy intentionally prevents collaborative editing of another user's transient draft; persistent ledger records retain their existing role visibility. Native administrator/superuser remains trusted.

## Recommendations and methodology limits

Merge only after reviewing the exact branch results and remaining risks. Real-data use remains gated by dependency/vendor triage and an actual hardened hosting/recovery/account plan. The skill workflow was performed through manual source/history/caller tracing and adversarial fixtures, not an installed Trail of Bits command or an independent second reviewer. No subagent or full framework security audit is claimed. Confidence is higher for reproduced custom-code defects and regression outcomes than for untested production infrastructure or third-party components.


## Final disposition

The corrected executable head `9adc18ccf89c1ecda7594689335b821d51b246e3` passed official-image integration, all 187 native methods, startup/restart, actual Chrome/PDF/runtime and separate-DB restore in workflow `41232041040`. Security workflow `41232040829` passed source/history gates while visibly retaining dependency advisory findings. The first CI recovery failure is preserved in `verification.md`, along with the matching-client correction and rerun evidence. **Ready for code review for the synthetic pilot; not approved for real-data deployment.** Subsequent documentation-only changes do not alter the tested executable source.
