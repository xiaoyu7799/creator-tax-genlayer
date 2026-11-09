# Reviewer fast path

Shortest way to re-check this contract without running the whole flow.
Network: Stable Studionet (chain 61999), RPC `https://studio.genlayer.com/api`.

## 1. The contract is the deployed code

- Contract: see `deployment.json` (`contractAddress`, `deployTxHash`).
- `deployment.json` records `contractSha256` and `deployedCodeSha256` (equal).
- Re-check: fetch `gen_getContractCode` for the address, base64-decode it,
  SHA-256 it, compare with `contracts/creator_tax.py`.

## 2. The money reconciles

- `get_ledger` returns `total_received_wei`, `total_paid_out_wei`,
  `funding_pool_wei`, `reserved_rewards_wei`, `open_stakes_wei`,
  `credits_wei`, `pending_tribute_wei`, `contract_balance_wei`,
  `stray_wei`, `invariant_ok`.
- Check: `total_received == total_paid_out + funding_pool + reserved_rewards
  + open_stakes + credits + pending_tribute`, and `contract_balance ==
  total_received - total_paid_out`, and `invariant_ok` is true.
- `evidence.json` records the same ledger plus a per-account EOA
  reconciliation (funded − sent + withdrawn == actual balance).

## 3. The three paths that matter

- Failed dispute (work 0, "Neon Koi"): round 1 KEEP, weak counter-evidence,
  round 2 KEEP → CONFIRMED, 4 GEN stake forfeited into the pool.
- Successful dispute (work 1, "Dust Choir"): round 1 KEEP, counter-evidence
  proving earlier creation (2026-09-20 vs 2026-10-05), round 2 REASSIGN →
  REASSIGNED, CONTRADICTION witness, challenger credited 4 GEN refund +
  1 GEN reward, later tribute routes to the new creator (see the
  post-reassignment 10 GEN transfer in `evidence.json`).
- Thin evidence (work 2, "Thin Sketch"): round 1 NOT_ESTABLISHED → DISPUTED,
  then dispute + round 2 REASSIGN.
- Rate change (work 0): 200bp proposal approved (stake refunded), a 10 GEN
  transfer then pays 0.2 GEN tribute; 0bp proposal rejected (stake
  forfeited), a further 10 GEN transfer still pays 0.2 GEN.
- Exact splits: 10 GEN at 100bp → 9.9 recipient + 0.1 tribute;
  7 GEN → 6.93 + 0.07; 25 GEN → 24.75 + 0.25. All read back on-chain
  in `evidence.json` and `docs/live-verification.md`.

## 4. The equivalence rule

- `docs/mechanism.md` has the worst-case spread table: every stored core
  value (rate tier, creator, tribute) has spread 0 between any two
  validator-compatible leader outputs, because equivalence requires exact
  equality of the verdict and of the SHA-256 of every fetched evidence body.

## 5. Tests

- `python3 tests/test_local.py` — local mock checks of the deterministic
  logic (split math, tiers, SHA-256, ledger bucket moves). Marked
  LOCAL MOCK ONLY; it is not on-chain evidence.
- `node scripts/flow.mjs` — the full on-chain run that produced
  `evidence.json` (needs a fresh deployment for a re-run).
