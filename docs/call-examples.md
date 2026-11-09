# Call examples

Network: Stable Studionet (chain 61999), RPC `https://studio.genlayer.com/api`.
Contract address and deployment record: `deployment.json`. All examples use
`genlayer-js` 1.1.8. Accounts below are ephemeral test accounts; the contract
is permissionless.

```js
import { createClient, createAccount, generatePrivateKey } from "genlayer-js";
import { studionet } from "genlayer-js/chains";

const address = "<contract address from deployment.json>";
const account = createAccount(generatePrivateKey());
const client = createClient({ chain: studionet, account });
const GEN = 10n ** 18n;

// Fund a test account (Studionet faucet equivalent).
await client.request({ method: "sim_fundAccount", params: [account.address, 100 * 10 ** 18] });

// Fund the sponsorship pool.
await client.writeContract({ address, functionName: "deposit_funding", args: [], value: 50n * GEN });

// Register a work (rate starts at 100bp).
const workId = await client.writeContract({
  address, functionName: "register_work",
  args: ["Neon Koi", "https://raw.githubusercontent.com/xiaoyu7799/creator-tax-genlayer/main/evidence/work-neon-koi.json", "Neon koi illustration."],
});

// Sponsor a work: 10 GEN, recipient gets 9.9 GEN credit, creator accrues 0.1 GEN pending tribute.
await client.writeContract({
  address, functionName: "transfer_with_tribute",
  args: [0n, "0xRecipientAddress..."], value: 10n * GEN,
});

// Read the work back.
const work = JSON.parse(await client.readContract({ address, functionName: "get_work", args: [0n] }));

// First attribution round (anyone except the creator): reads the original evidence only.
await client.writeContract({ address, functionName: "resolve_attribution", args: [0n] });

// Dispute the attribution (4 GEN stake, counter-evidence URL is required).
await client.writeContract({
  address, functionName: "dispute_attribution",
  args: [0n, "0xClaimedCreator...", "https://.../counter-evidence.json", "Claim note."],
  value: 4n * GEN,
});

// Second attribution round: reads the original evidence AND the counter-evidence.
await client.writeContract({ address, functionName: "resolve_attribution", args: [0n] });

// Propose a new rate tier (current creator only, 1 GEN stake, tiers 0 / 100 / 200bp).
await client.writeContract({
  address, functionName: "propose_rate",
  args: [0n, 200n, "https://.../rate-rationale.json", "Rationale note."],
  value: 1n * GEN,
});

// Resolve the rate proposal (anyone except the proposer).
await client.writeContract({ address, functionName: "resolve_rate", args: [0n] });

// Claim pending tribute for a work (current creator only), then withdraw.
await client.writeContract({ address, functionName: "claim_credit", args: [0n] });
await client.writeContract({ address, functionName: "withdraw_credit", args: [] });

// Ledger, pool, credits, leaderboard.
const ledger = JSON.parse(await client.readContract({ address, functionName: "get_ledger", args: [] }));
const pool = JSON.parse(await client.readContract({ address, functionName: "get_funding_pool", args: [] }));
const credit = JSON.parse(await client.readContract({ address, functionName: "get_credit", args: [account.address] }));
const board = JSON.parse(await client.readContract({ address, functionName: "get_leaderboard", args: [10n] }));
```

Notes:

- A write's receipt `result` field is not the success signal: judge a call by
  the on-chain state change it produces (see `scripts/flow.mjs`, which
  re-reads state after every resolve and retries on no-consensus).
- A rejected payable call leaves its attached GEN in the contract balance
  as stray; `sweep_stray_gen` moves it into the pool. See `docs/mechanism.md`.
- Evidence URLs must be live (HTTP 200) when a resolve runs, because the
  judges fetch them at evaluation time.
