# Mechanism

## What this is, in four lines

- **Category:** Creator / token — a sponsorship layer for creative works, where every transfer pays a small tribute to the work's creator.
- **Mechanism:** Consensus decides two things: (a) attribution disputes — who is the lawful creator of a work; (b) tribute-rate proposals — whether the creator may move the rate between tiers. Consequences: the creator registration changes, later tribute routes to the new creator, dispute stakes are forfeited or refunded with a reward, and rate-proposal stakes are refunded or forfeited.
- **Interaction model:** A creator registry plus a live tribute ledger — register a work, sponsor it, dispute it, propose a rate. No store-and-list shell: the money flow and the adjudication are the product.
- **Evolving state:** Cumulative tribute earned per creator, attribution wins and losses from zero, rate history per work, and a leaderboard ranked by tribute earned.

## Money flow (real testnet GEN, 1 GEN = 10^18 wei)

- **Sponsorship transfer** (`transfer_with_tribute`, payable, any amount): tribute = amount × rate_bp / 10000, integer division, remainder to the recipient. The recipient's share becomes an immediately withdrawable credit; the tribute becomes pending tax for the work's current creator. The creator moves it to a withdrawable credit with `claim_credit` (per work), then withdraws with `withdraw_credit` (pull payment: the credit is zeroed before the transfer).
- **Tribute rate tiers:** only 0 / 100 / 200 basis points. Default 100bp (1%). No other tier can ever be stored — `propose_rate` rejects anything else.
- **Attribution dispute** (`dispute_attribution`, payable, exactly 4 GEN): the challenger names a claimed creator and supplies a counter-evidence URL, which is stored in the dispute. 1 GEN is reserved from the sponsorship pool at dispute time so a later success reward is always covered. If the second evaluation keeps the registered creator, the 4 GEN stake plus the 1 GEN reservation go into the pool. If it reassigns the work, the challenger is credited 4 GEN (stake refund) + 1 GEN (reward), the first pending attribution is kept as a CONTRADICTION witness, and later tribute routes to the new creator.
- **Rate proposal** (`propose_rate`, payable, exactly 1 GEN, current creator only): the creator proposes a new tier with a rationale URL. If the evaluation approves, the rate changes and the 1 GEN stake is refunded as a credit. If it rejects, the stake is forfeited into the pool and the rate is unchanged.
- **Sponsorship pool** (`deposit_funding`, payable): anyone may fund it; the on-chain flow funds it with 50 GEN. The pool pays dispute success rewards (via the reservation) and absorbs forfeited stakes.
- **Stray GEN** (`sweep_stray_gen`): a payable call the contract rejects still leaves its attached GEN in the contract balance (the state change rolls back, the value transfer does not). That GEN is visible as `stray_wei` in `get_ledger` and is swept into the pool, adjusting `total_received` by the same amount so the invariant holds again.

## The two attribution rounds have different inputs

This is the load-bearing design decision. Round 1 (`resolve_attribution` with no open dispute) reads **only** the original registration evidence and returns ESTABLISHED (the evidence explicitly states a creation date and a verifiable anchor tying the work to the registered creator) or NOT_ESTABLISHED (no date, no anchor — the work is marked DISPUTED). A dispute can only open after round 1, and it must carry a counter-evidence URL. Round 2 (`resolve_attribution` with an open dispute) fetches **both** the original evidence and the counter-evidence and returns KEEP or REASSIGN — REASSIGN only if the counter-evidence explicitly proves the claimed creator created the work earlier, with both an earlier explicit creation date and a verifiable anchor.

Because round 2 sees evidence round 1 never saw, a flip has a real mechanism behind it. A challenge that merely re-runs the same evidence cannot flip anything: the judge is deterministic on explicitly stated facts, so the same input gives the same verdict. The flip path is exercised on-chain in `evidence.json` (works 1 and 2), and the fail path (weak counter-evidence, KEEP, stake forfeited) is exercised on work 0.

## Equivalence and the worst-case spread

A validator accepts a leader output only if it equals the validator's own output **exactly**: same verdict, and the same SHA-256 of **every** fetched evidence body. There is no tolerance, no score band, no threshold anywhere. The verdict vocabularies are fixed and binary (round 1: ESTABLISHED / NOT_ESTABLISHED; round 2: KEEP / REASSIGN; rate: APPROVE / REJECT), and the tribute split is deterministic integer division.

| Core value | What two passing leaders could store | Worst-case spread | Smallest meaningful difference | Changes the business outcome? |
|---|---|---|---|---|
| Rate tier (bp) | Both must store the same tier from {0, 100, 200} | 0 bp | 1 bp (the gap between adjacent tiers is 100 bp) | No |
| Attribution verdict | Both must store the same verdict from {KEEP, REASSIGN} | 0 — same creator, or same reassignment | A creator either changes or does not; there is no partial reassignment | No |
| Tribute (wei) | Same amount and same tier give the same integer division | 0 wei | 1 wei | No |
| Rate-proposal verdict | Both must store the same verdict from {APPROVE, REJECT} | 0 — same stored rate | 1 bp | No |
| Evidence identity | Both must report the same SHA-256 for each fetched body | 0 — identical bytes | Any byte differs | No |

Edge cases, not just the happy path: a 1-wei transfer at 100bp yields 0 tribute and a 1-wei recipient share for every validator (spread 0). A 3-GEN transfer at 200bp yields 0.06 GEN tribute exactly. Two leaders that both pass cannot disagree on any of these, because any disagreement in verdict or evidence hash is a rejection, not a stored value.

Two further rules: evidence fetched at different times is not treated as the same evidence — each round stores the SHA-256 of the bytes it actually fetched, so a changed file is visible as a different hash, not silently equated. And a finalized attribution is never changed: a work that is CONFIRMED or REASSIGNED cannot be disputed again (one dispute per work).

## States

- Work: REGISTERED → ATTRIBUTION_REVIEW → CONFIRMED / DISPUTED / REASSIGNED. DISPUTED means round 1 found the original evidence unable to establish the creator (attribution unproven); the work can still be disputed and decided in round 2. CONFIRMED means round 2 kept the registered creator. REASSIGNED means round 2 reassigned the work to the claimed creator.
- Rate proposal: RATE_PENDING → RATE_ACTIVE (resolved), with outcome APPROVE or REJECT recorded on the proposal.
- There is no deadline anywhere: the network has no clock source, so a dispute or a proposal stays open until someone resolves it. That is a product property, not an oversight — see KNOWN_LIMITATIONS.md.

## Ledger invariant

```
total_received == total_paid_out + funding_pool + reserved_rewards
                   + open_stakes + credits + pending_tribute
contract_balance == total_received - total_paid_out
```

`get_ledger` reports every bucket plus `stray_wei` (contract balance minus accounted) and `invariant_ok`. The on-chain flow checks the invariant twice: once from the contract's own flag, once recomputed from the returned buckets with BigInt arithmetic, and additionally reconciles every account's EOA balance as funded − sent + withdrawn.

## Functions

| Function | Who | Value | Effect |
|---|---|---|---|
| `deposit_funding` | anyone | > 0 GEN | Adds to the sponsorship pool |
| `register_work(title, evidence_url, evidence_note)` | anyone | 0 | New work, REGISTERED, rate 100bp |
| `transfer_with_tribute(work_id, recipient)` | anyone | > 0 GEN | Splits amount into recipient credit + pending creator tribute |
| `resolve_attribution(work_id)` | anyone except the work's creator | 0 | Round 1 (no dispute) or round 2 (dispute open) |
| `dispute_attribution(work_id, claimed_creator, counter_evidence_url, counter_note)` | anyone except the work's creator | exactly 4 GEN | Opens a dispute, reserves 1 GEN reward |
| `propose_rate(work_id, new_rate_bp, rationale_url, rationale_note)` | current creator only | exactly 1 GEN | Opens a rate proposal |
| `resolve_rate(work_id)` | anyone except the proposer | 0 | Approves or rejects the proposal |
| `claim_credit(work_id)` | current creator only | 0 | Moves the work's pending tribute to a withdrawable credit |
| `withdraw_credit()` | anyone with a credit | 0 | Pull payment of the full credit to the caller's address |
| `sweep_stray_gen()` | anyone | 0 | Moves unaccounted GEN into the pool |

Views: `get_work`, `get_work_count`, `list_works`, `get_credit`, `get_creator_stats`, `get_funding_pool`, `get_ledger`, `get_leaderboard`.
