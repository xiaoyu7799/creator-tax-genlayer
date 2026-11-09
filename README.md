# Creator Tax

Creator trading-tax sponsorship on GenLayer: every sponsorship transfer pays a small tribute to a work's creator, and consensus decides who the lawful creator is and what the tribute rate should be.

- **What it does:** register a creative work with authorship evidence; sponsor it with real testnet GEN (tribute split by integer division, remainder to the recipient); dispute the attribution with counter-evidence (the second evaluation reads both evidence sets, so a flip has a real mechanism behind it); propose a rate change between 0 / 100 / 200 basis points. Tribute and rewards are pull-paid.
- **Network:** Stable Studionet only (chain 61999), RPC `https://studio.genlayer.com/api`.
- **Contract:** `0xCc792333d8931791Cad14EB3dc473e666B40b28F` (see `deployment.json` for the deployment transaction and source SHA-256)

## Deployment

- Contract: `0xCc792333d8931791Cad14EB3dc473e666B40b28F`
- Deployment transaction: `0xaa455c9dc76c83d97519c7da74409ea0b924165338a41503e6304903d0cdc4d4` (FINALIZED)
- Explorer: `https://explorer-studio.genlayer.com/address/0xCc792333d8931791Cad14EB3dc473e666B40b28F`
- Source: `contracts/creator_tax.py` (SHA-256 `a6c8eaeea4e814fc2dea98736eac0493848043f0e2e92c73655e18dbafdd4166`, verified equal to the deployed code)

## How it works

| Step | Call | Economics |
|---|---|---|
| Fund the pool | `deposit_funding` (payable) | Any amount; the flow uses 50 GEN |
| Register a work | `register_work(title, evidence_url, note)` | Free; rate starts at 100bp |
| Sponsor a work | `transfer_with_tribute(work_id, recipient)` (payable) | Tribute = amount × rate / 10000, integer division |
| Attribute (round 1) | `resolve_attribution(work_id)` | Reads the original evidence only |
| Dispute | `dispute_attribution(work_id, claimed_creator, counter_url, note)` (payable) | Exactly 4 GEN stake; 1 GEN reward reserved from the pool |
| Attribute (round 2) | `resolve_attribution(work_id)` | Reads original + counter-evidence; KEEP or REASSIGN |
| Change the rate | `propose_rate(work_id, new_rate_bp, rationale_url, note)` (payable) | Exactly 1 GEN stake; tiers 0 / 100 / 200bp |
| Resolve the rate | `resolve_rate(work_id)` | APPROVE (rate changes, stake refunded) or REJECT (stake forfeited) |
| Claim + withdraw | `claim_credit(work_id)`, `withdraw_credit()` | Pull payment |

## Evidence

- `evidence.json` — machine-readable record of the on-chain flow: every transaction hash and FINALIZED status, rejected calls, read-back state, ledger, and GEN reconciliation (total in == total out + pool + credits + pending).
- `docs/live-verification.md` — the same record as readable text.
- `docs/mechanism.md` — the mechanism, the two-round attribution design, and the worst-case spread table (spread 0 on every stored core value).
- `docs/reviewer-fast-path.md` — the shortest re-verification steps.
- `docs/call-examples.md` — how to call every function.
- `KNOWN_LIMITATIONS.md` — product limits (one dispute per work, no deadlines, evidence must stay reachable, coarse rate tiers).

## Tests

- `python3 tests/test_local.py` — local mock checks of the deterministic logic (split math, tiers, SHA-256, ledger moves). Marked LOCAL MOCK ONLY; not on-chain evidence.
- `node scripts/flow.mjs` — the full on-chain flow that produced `evidence.json`.
- `node scripts/deploy.mjs` — deploys the contract and verifies the deployed code SHA-256 against the source.

## Work states

`REGISTERED → ATTRIBUTION_REVIEW → CONFIRMED / DISPUTED / REASSIGNED`; rate proposals go `RATE_PENDING → RATE_ACTIVE`. Creator evolution (tribute earned, attribution wins/losses, rate outcomes) is tracked from zero and ranked in `get_leaderboard`.
