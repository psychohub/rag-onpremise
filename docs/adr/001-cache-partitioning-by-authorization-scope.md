# ADR-001: Cache partitioning by authorization scope

**Date:** August 2026
**Status:** Accepted
**Author:** Hubert García Gordon

Raised by Ivan Rossouw in the discussion thread of "On-premise RAG
without GPU, cloud, or Docker" on dev.to.

---

## Context

The reference implementation caches generated answers keyed on the
semantic similarity of the incoming question. As originally published,
the lookup happened before the target collection was resolved, so a
semantically similar question scoped to one collection could return an
answer and sources produced for another. Ivan Rossouw reported this in
the article thread.

In the single-collection scenario the repository ships, it was not
exploitable: there is only one scope, so there was nothing to cross. It
would have become a real leak vector the moment the code was extended to
multiple collections, which is the first thing any non-trivial
deployment does.

Commit `6f22c11` closed it. The collection is now resolved before the
lookup and is the first component of the cache key, so cosine similarity
is only ever computed between entries of the same collection.

That fix covers collection. It does not cover the rest of what an answer
is scoped to, and the repository has no concept of an authenticated
caller at all. This ADR records how cache entries should be partitioned
so that the extensions a real deployment will make are safe by default
rather than safe by accident.

### Authorization model assumed

- Permissions are **role-based**. An external identity system assigns a
  profile; this repository does not implement or prescribe one.
- A role grants access to **entire collections**, not to individual
  documents within a collection.
- The repository currently ships one collection. The design targets
  several.
- **Revocation must take effect immediately.** A user who loses a role
  must not be able to read anything produced under it, including from
  cache.

### Related constraint

The answer cache is disabled by default (`SemanticCacheEnabled = false`)
for reasons unrelated to authorization: cosine similarity between
question embeddings does not reliably separate a question from its
negation, so a hit can serve a confidently wrong answer with no signal.
See `docs/experiments/threshold-safety.md`.

That decision does not remove the need for this one. The partitioning
described here applies whenever the cache is enabled, and the retrieval
layer proposed in the decision below would not be subject to the same
failure mode.

## Decision

### 1. Two layers, partitioned differently

**Answer cache** — question to generated answer. Partitioned by
authorization scope. Small, low sharing. The repository ships this
layer, but not the authorization-scope component of its key; see
*Implementation status*.

**Retrieval cache** — query embedding to candidate source IDs and
scores. Shared across all roles that can reach the collection. Larger,
high sharing, and it would hold the expensive part of the pipeline. This
layer is proposed, not implemented; see section 3 and *Implementation
status*.

The split exists because the two layers carry different risk. A
retrieval hit returns candidates and the model still processes the
actual incoming question against them. An answer hit returns text
produced for a different question and nothing downstream can notice.

### 2. Composite key on the answer cache

Matching happens in two tiers, and keeping them distinct is the whole
point of this section:

1. **The key partitions by exact match.** Every component below must be
   identical for two entries to live in the same partition.
2. **Similarity search happens only inside a partition.** The incoming
   question is compared by cosine similarity against the embeddings
   stored there, and nothing outside the partition is a candidate.

The key covers:

| Component | Bounds | In `BuildCacheKey` today |
|---|---|---|
| collection identifier | who and what | yes |
| authorization scope (the role set that resolved the request) | who and what | **no** |
| corpus revision | state of the world | **no** |
| authorization-policy revision | state of the world | **no** |
| embedding model identifier | how it was computed | yes |
| chat model identifier | how it was computed | yes |
| prompt version | how it was computed | yes |
| retrieval top-K | how it was computed | yes |

Five of the eight are shipped. The three missing ones are not omissions
in `BuildCacheKey`; they are inputs the repository does not have. There
is no authenticated caller to derive a role set from, no corpus revision
counter, and no authorization policy to version. Adding them to the key
is the last step of that work, not the first.

The two revision rows are the part most easily missed. Corpus revision and
authorization-policy revision are not properties of the request. They
are properties of the system at the moment of generation, and an answer
computed before a document was withdrawn is stale even though nothing
about the request changed.

**The question itself is deliberately not a key component.** A composite
key matches exactly, so putting the question in it would turn the cache
into a lookup table keyed on literal string equality — which removes the
reason a semantic cache exists. The key answers *which entries may this
question be compared against at all*; the similarity threshold answers
*is this entry close enough to serve*. Two different questions, and
conflating them produces either a cache that never hits or one that
partitions by nothing.

The second tier is the one `docs/experiments/threshold-safety.md` found
unsafe with this embedder and corpus. That is a limitation of similarity
matching, not of partitioning, and it is why the cache ships disabled.
Partitioning bounds *what a wrong hit can reach*; it does not prevent
the hit from being wrong.

### 3. Retrieval cache stores source IDs, not content

> **Proposed. No retrieval cache exists in the repository.** The
> `RagService` ships one cache, the answer cache. This section describes
> a layer to be built, not code to be audited.

The retrieval layer would cache candidate identifiers and scores, keyed
on query embedding, collection, embedding model and corpus revision. It
would not cache chunk text and would not cache authorization outcomes.

On every retrieval hit it would:

1. Confirm the requesting role set currently grants the collection.
2. Re-resolve the candidates against the current corpus revision.
3. If any candidate no longer resolves, backfill from vector search
   before generation rather than proceeding with a short list.

Caching the authorization outcome alongside the candidates would turn a
revocation into a delayed leak. The check is cheap under
whole-collection roles and should be performed every time.

This is the chunk-level cache Ivan Rossouw proposed in the same thread,
also recorded as a possible mitigation in
`docs/experiments/threshold-safety.md` §5.3.

### 4. Immediate revocation follows from the key, not from a sweep

> **Proposed.** This follows from the three key components that are not
> implemented; it describes what the design buys once they exist.

Because the role set is part of the answer-cache key, a user who loses a
role stops matching the partitions written under it. Their next request
carries a different key and cannot hit those entries. No invalidation
pass is required and there is no window.

Two changes would otherwise require invalidation, and both are handled
by the key rather than by eviction logic:

- A document added to or withdrawn from a collection bumps the corpus
  revision, so prior entries become unreachable.
- A change in what a role grants bumps the authorization-policy
  revision, with the same effect.

Entries left unreachable are removed by ordinary expiry. Correctness
does not depend on that removal happening promptly.

## Implementation status

This ADR records a decision. Most of it is not code yet, and this table
is the authoritative statement of which is which. Verified against
`dotnet/RagService.cs`, `dotnet/RagSettings.cs`, `dotnet/RagController.cs`
and `dotnet/IRagService.cs` at commit `d93eab5`.

| Element | Status | Where |
|---|---|---|
| Answer cache exists | Shipped | `RagService.cs`, `SearchCacheAsync` / `SaveToCacheAsync` |
| Answer cache disabled by default | Shipped | `RagSettings.SemanticCacheEnabled = false` |
| Partition by collection | Shipped | `BuildCacheKey` |
| Partition by embedding model, chat model, prompt version, top-K | Shipped | `BuildCacheKey` |
| Similarity match confined to the partition | Shipped | `SearchCacheAsync` iterates one partition only |
| Cancellation reaches the vector store, model and deserialization calls | Shipped | `RagService.cs`, all call sites |
| Cancellation reaches the entry point | Shipped | `RagController` passes `HttpContext.RequestAborted`; `d93eab5` |
| Partition by authorization scope | **Design** | Requires an authenticated caller; none exists |
| Partition by corpus revision | **Design** | Requires a revision counter; none exists |
| Partition by authorization-policy revision | **Design** | Requires a versioned policy; none exists |
| Retrieval cache (section 3) | **Design** | No such layer in the repository |
| Re-check of role grant on retrieval hit | **Design** | Follows from the retrieval cache |
| Backfill of unresolved candidates | **Design** | Follows from the retrieval cache |
| Measured bound on generation-slot release | **Not done** | See criterion 5 |

The repository is reference material and has no `.csproj`, so none of
the shipped rows are verified by a build in CI. They were verified by
reading the code and by compiling it against a throwaway harness.

## Alternatives considered

**Per-user partitioning.** The safest option: every user gets their own
entries and nothing is shared. Rejected because under whole-collection
roles it buys no additional safety. Two users with identical role sets
are entitled to identical results, so separating them fragments the
cache without closing any exposure. This would be the right choice under
document-level permissions, where two users with the same role can still
be entitled to different subsets.

**Role partitioning with a time-bounded staleness window.** Simpler
invalidation, at the cost of a period during which a revoked user can
still read cached output. Rejected: revocation has to be immediate, and
a design that tolerates a window in a reference implementation invites
someone to widen it.

**Single-layer answer cache with a composite key.** Fewer moving parts.
Rejected because it caches the wrong thing. The expensive work is
embedding and vector search, which is shareable; the risky work is
generation, which is not. One layer forces the same partitioning on
both and gives up most of the sharing to protect the smaller half.

**Caching authorization outcomes with the candidates.** Faster hits.
Rejected outright: it converts a revocation into a delayed leak, which
is the exact failure this ADR exists to prevent.

## Consequences

### Gained

These are the properties of the design once complete. Only the first is
partly in effect today, and only for collection.

- Cross-scope reuse is prevented by key construction rather than by a
  check that can be forgotten in a later refactor.
- Revocation is immediate for role changes without an invalidation
  sweep.
- The expensive half of the pipeline stays shareable across roles.
- Stale corpus and stale policy are handled by the same mechanism as
  stale models and prompts, rather than by a separate path.

### Given up

- Hit rate on the answer cache. Two users with different role sets
  asking the same question generate two entries.
- Every corpus revision bump invalidates the entire answer cache for the
  affected collection. Under frequent ingestion this may make the answer
  layer uneconomical, and the retrieval layer would carry most of the
  benefit.
- Key size and complexity. Eight components is more surface for a
  mistake, which is part of why this document exists.

### Out of scope

- **Document-level permissions.** The design assumes whole-collection
  roles. Under per-document access, role-based sharing is no longer
  sufficient and both the partitioning and the hit-time check need
  revisiting. That would supersede this ADR rather than amend it.
- **Identity and role assignment.** Out of scope by intent. The
  repository consumes a role set and does not prescribe where it comes
  from.
- **The negation problem.** Partitioning does not address it. It is
  handled separately by leaving the answer cache disabled by default.

## Acceptance criteria

Proposed by Ivan Rossouw in the same thread and adopted as written:

1. The same question issued against collections A and B must not return
   an answer produced for the other.
2. After a role change, cached output produced under the previous role
   set must be unreachable.
3. After a document is withdrawn, candidates referencing it must be
   rejected and the shortlist backfilled from vector search before
   generation.
4. Bumping prompt version, model identifier or retrieval top-K must
   miss.
5. Disconnecting a request must release the generation slot within a
   measured bound.

Criteria 1 and 4 are testable against the code as it stands: collection,
both model identifiers, prompt version and top-K are all in
`BuildCacheKey`. Criteria 2 and 3 are not, because they depend on the
authorization scope, corpus revision and retrieval layer listed as
design above. Neither is written as a test anywhere — the repository has
no test project.

Criterion 5 is not yet satisfiable as stated, for a narrower reason than
when this ADR was first drafted. Cancellation now propagates end to end:
`RagController` passes `HttpContext.RequestAborted`, `IRagService`
carries the token in its contract, and every downstream call — vector
store, model, deserialization and the cache lock waits — receives it.
Until commit `d93eab5` this was not true. `6f22c11` had added the token
inside `RagService` but not to the interface or the controller, so the
token reaching those calls was always `CancellationToken.None`, and the
service no longer satisfied its interface. The regression survived
because the repository has no build.

What remains unmet is the measurement. Nothing instruments how long the
generation slot takes to release after a disconnect, so the bound in the
criterion is unmeasured rather than met. The plumbing is a precondition
for that measurement, not a substitute for it.

## References

- Thread: Ivan Rossouw, comments of 1 and 8 August 2026 on
  "On-premise RAG without GPU, cloud, or Docker" (dev.to).
- `docs/experiments/threshold-safety.md` — why the answer cache is
  disabled by default.

---

*This is a personal open-source project. It describes no institutional
deployment and uses no data from any production system.*
