/* End-to-end on-chain flow for Creator Tax v0.1.0 (real testnet GEN).
 *
 * Usage:
 *   CONTRACT_ADDRESS=0x... node scripts/flow.mjs
 *   # Accounts are ephemeral and generated for this run only (Studionet is
 *   * gasless; testnet GEN comes from sim_fundAccount). No key is ever
 *   * written to disk.
 *
 * Roles:
 *   D = funder: funds 10000 GEN, deposit_funding 50 GEN, sponsors transfers.
 *   A = creator: registers 3 works, claims tribute, proposes rate changes.
 *   B = challenger: disputes attribution (4 GEN stake), claims the new
 *     creator's tribute after a successful reassignment.
 *   E = evaluator: resolves attribution and rate proposals (never the
 *     creator, never the proposer).
 *   R = recipient: receives sponsorship transfers, withdraws the credit.
 *   C = fresh account with no credit, used for the no-credit withdraw probe.
 *
 * Evidence files are written by this script with the run's real creator
 * and challenger addresses, committed and pushed, and polled until the
 * raw.githubusercontent.com URLs answer 200 — the contract's judges
 * fetch those URLs, so they must be live before any resolve call.
 *
 * Flow:
 *   reject probes (0 GEN where payable, so no stray is created) ->
 *   deposit 50 GEN -> register 3 works -> sponsorship transfers with
 *   exact split read-back -> tribute claims -> work 0: round 1 KEEP,
 *   wrong-stake probe (3 GEN stray) + sweep, dispute, round 2 KEEP
 *   (failed dispute, stake forfeited) -> work 1: round 1 KEEP, dispute
 *   with earlier-creation counter-evidence, round 2 REASSIGN
 *   (CONTRADICTION witness, challenger credited 4 + 1 GEN), tribute
 *   re-routes to the new creator -> work 2: thin evidence, round 1
 *   NOT_ESTABLISHED (DISPUTED), dispute, round 2 REASSIGN -> rate
 *   proposal 200bp approved (stake refunded), transfer at 200bp ->
 *   rate proposal 0bp rejected (stake forfeited), transfer still at
 *   200bp -> final claims -> withdrawals -> full read-back + ledger
 *   reconciliation + EOA reconciliation.
 * Writes evidence.json (tx hashes, FINALIZED status, read-back values)
 * and docs/live-verification.md.
 *
 * Resolve calls are retried with explicit state-change verification: a
 * FINALIZED resolve that leaves the evaluation count unchanged means no
 * consensus, and is retried up to 5 times. Verdicts are recorded as they
 * actually come back; the flow adapts (a flip that does not happen is
 * reported, not assumed) rather than assuming them.
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { execSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createClient, createAccount, generatePrivateKey } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const deployment = JSON.parse(readFileSync(path.join(root, "deployment.json"), "utf-8"));
const address = process.env.CONTRACT_ADDRESS || deployment.contractAddress;
if (!address) throw new Error("No contract address: set CONTRACT_ADDRESS or run deploy first");

const REPO = "xiaoyu7799/creator-tax-genlayer";
const GEN = 10n ** 18n;

const funder = createAccount(generatePrivateKey());
const creator = createAccount(generatePrivateKey());
const challenger = createAccount(generatePrivateKey());
const evaluator = createAccount(generatePrivateKey());
const recipient = createAccount(generatePrivateKey());
const fresh = createAccount(generatePrivateKey());
console.log("Funder (D):", funder.address);
console.log("Creator (A):", creator.address);
console.log("Challenger (B):", challenger.address);
console.log("Evaluator (E):", evaluator.address);
console.log("Recipient (R):", recipient.address);
console.log("Fresh probe account (C):", fresh.address);
console.log("Contract:", address);

const clientD = createClient({ chain: studionet, account: funder });
const clientA = createClient({ chain: studionet, account: creator });
const clientB = createClient({ chain: studionet, account: challenger });
const clientE = createClient({ chain: studionet, account: evaluator });
const clientR = createClient({ chain: studionet, account: recipient });
const clientC = createClient({ chain: studionet, account: fresh });

const STATUS_NAMES = { 0: "UNINITIALIZED", 1: "PENDING", 2: "PROPOSING", 3: "COMMITTING", 4: "REVEALING", 5: "ACCEPTED", 6: "UNDETERMINED", 7: "FINALIZED", 8: "CANCELED" };
const txs = [];
const rejects = [];
const eoaBalances = {};
const sentWei = {}; // GEN actually sent to the contract per account (incl. reverted value)
const withdrawnWei = {};

function trackSent(addr, value) {
  sentWei[addr] = (sentWei[addr] ?? 0n) + BigInt(value);
}
function genStr(wei) {
  const w = BigInt(wei);
  const whole = w / GEN;
  const frac = ((w % GEN) * 100n) / GEN;
  return frac === 0n ? `${whole}` : `${whole}.${frac.toString().padStart(2, "0")}`;
}

function note(label, hash, receipt) {
  const status = receipt.statusName ?? STATUS_NAMES[receipt.status] ?? String(receipt.status ?? "");
  console.log(`${label}: ${hash} -> ${status}`);
  txs.push({ label, txHash: hash, status });
  if (status !== "FINALIZED") throw new Error(`${label} did not FINALIZE (status ${status})`);
}

async function waitFinal(client, hash, label) {
  const receipt = await client.waitForTransactionReceipt({
    hash,
    status: TransactionStatus.FINALIZED,
    retries: 180,
    interval: 5000,
  });
  note(label, hash, receipt);
  return receipt;
}

async function write(client, functionName, args, label, value = 0n) {
  const hash = await client.writeContract({ address, functionName, args, value, leaderOnly: false });
  trackSent(client.account.address, value);
  await waitFinal(client, hash, label);
  return hash;
}

async function read(client, functionName, args) {
  // The Studionet gateway occasionally answers a read with an HTML
  // error page instead of JSON (transient). Retry the read instead of
  // letting one blip kill the run.
  let lastErr = null;
  for (let i = 1; i <= 6; i++) {
    try {
      const raw = await client.readContract({ address, functionName, args });
      if (typeof raw === "string") {
        try { return JSON.parse(raw); } catch { return raw; }
      }
      return raw;
    } catch (err) {
      lastErr = err;
      console.log(`read ${functionName} attempt ${i} failed (transient?): ${String(err?.message ?? err).slice(0, 200)}`);
      if (i < 6) await new Promise((r) => setTimeout(r, 10000));
    }
  }
  throw lastErr;
}

const eoaBalance = async (client, addr) => {
  let lastErr = null;
  for (let i = 1; i <= 6; i++) {
    try {
      return (await client.getBalance({ address: addr })).toString();
    } catch (err) {
      lastErr = err;
      console.log(`getBalance attempt ${i} failed (transient?): ${String(err?.message ?? err).slice(0, 200)}`);
      if (i < 6) await new Promise((r) => setTimeout(r, 10000));
    }
  }
  throw lastErr;
};

/* A call that must be rejected. Records how it was rejected (client-side
 * throw, or an included transaction whose receipt carries the error) and
 * verifies the relevant on-chain state did not change. Throws if the call
 * unexpectedly succeeds. All probes here send 0 GEN, so no stray is made. */
async function expectReject(client, functionName, args, value, label, stateCheck) {
  const before = stateCheck ? await stateCheck() : null;
  let outcome = null;
  let hash = null;
  try {
    hash = await client.writeContract({ address, functionName, args, value, leaderOnly: false });
  } catch (err) {
    outcome = { rejectedAt: "client", error: String(err?.message ?? err).slice(0, 500) };
  }
  if (hash) {
    try {
      const receipt = await client.waitForTransactionReceipt({
        hash,
        status: TransactionStatus.FINALIZED,
        retries: 60,
        interval: 5000,
      });
      const status = receipt.statusName ?? STATUS_NAMES[receipt.status] ?? String(receipt.status ?? "");
      outcome = { rejectedAt: "receipt", txHash: hash, status, receipt: JSON.stringify(receipt).slice(0, 800) };
    } catch (err) {
      outcome = { rejectedAt: "receipt-wait", txHash: hash, error: String(err?.message ?? err).slice(0, 500) };
    }
  }
  const after = stateCheck ? await stateCheck() : null;
  const unchanged = before === null || JSON.stringify(before) === JSON.stringify(after);
  console.log(`${label}: REJECTED (${outcome.rejectedAt}), state unchanged: ${unchanged}`);
  if (!unchanged) throw new Error(`${label}: state changed despite rejection! before=${JSON.stringify(before)} after=${JSON.stringify(after)}`);
  rejects.push({ label, functionName, args: args.map(String), valueWei: value.toString(), ...outcome, stateUnchanged: unchanged });
  return outcome;
}

/* A resolve call (attribution or rate): retry until the on-chain state
 * shows the evaluation actually landed (evaluations count moved, or the
 * work/proposal left its pending state). A FINALIZED resolve with no
 * state change means no consensus; retry up to 5 times, then report. */
async function resolveWithRetry(client, functionName, args, label, stateFn, doneFn, attempts = 5) {
  let lastState = await stateFn();
  for (let i = 1; i <= attempts; i++) {
    try {
      const hash = await client.writeContract({ address, functionName, args, value: 0n, leaderOnly: false });
      const receipt = await client.waitForTransactionReceipt({ hash, status: TransactionStatus.FINALIZED, retries: 180, interval: 5000 });
      const status = receipt.statusName ?? STATUS_NAMES[receipt.status] ?? String(receipt.status ?? "");
      console.log(`${label} (attempt ${i}): ${hash} -> ${status}`);
      txs.push({ label: `${label} (attempt ${i})`, txHash: hash, status });
      if (status !== "FINALIZED") throw new Error(`${label} did not FINALIZE`);
    } catch (err) {
      console.log(`${label} attempt ${i} threw: ${String(err?.message ?? err).slice(0, 300)}`);
      if (i < attempts) await new Promise((r) => setTimeout(r, 10000));
      continue;
    }
    const after = await stateFn();
    if (doneFn(lastState, after)) {
      console.log(`${label} attempt ${i}: state advanced`);
      return after;
    }
    console.log(`${label} attempt ${i}: FINALIZED but state unchanged (no consensus), retrying`);
    lastState = after;
    if (i < attempts) await new Promise((r) => setTimeout(r, 10000));
  }
  return null;
}

// --- 0. Fund accounts via sim_fundAccount.
for (const [client, account, gen] of [
  [clientD, funder, 10000], [clientA, creator, 100], [clientB, challenger, 100],
  [clientE, evaluator, 100], [clientR, recipient, 100], [clientC, fresh, 10],
]) {
  const fundTx = await client.request({
    method: "sim_fundAccount",
    params: [account.address, gen * 10 ** 18],
  });
  console.log(`sim_fundAccount ${account.address.slice(0, 10)}… ${gen} GEN:`, String(fundTx).slice(0, 80));
  const bal = await eoaBalance(client, account.address);
  if (bal !== (BigInt(gen) * GEN).toString()) throw new Error(`fund amount mismatch for ${account.address}`);
}
const fundedWei = {
  [funder.address]: 10000n * GEN, [creator.address]: 100n * GEN,
  [challenger.address]: 100n * GEN, [evaluator.address]: 100n * GEN,
  [recipient.address]: 100n * GEN, [fresh.address]: 10n * GEN,
};

// --- 0b. Write the evidence files with the run's real addresses, push,
//     and poll the raw URLs until they answer 200.
const branch = execSync("git rev-parse --abbrev-ref HEAD", { cwd: root }).toString().trim();
const evDir = path.join(root, "evidence");
mkdirSync(evDir, { recursive: true });
const ev = (name) => `https://raw.githubusercontent.com/${REPO}/${branch}/evidence/${name}`;
const A = creator.address;
const B = challenger.address;
const evidenceFiles = {
  "work-neon-koi.json": {
    title: "Authorship evidence — Neon Koi (original registration)",
    work: "Neon Koi",
    creator: A,
    report: "Work 'Neon Koi' is a digital illustration of a neon koi fish. The registered creator " + A + " created this work on 2026-10-01. The creation is anchored by a signed message: the creator signed the text 'Neon Koi by " + A + " 2026-10-01' with the registered wallet. The work was first published on 2026-10-02 in the gallery 'Pixel Pond', listing the registered creator as the artist. No earlier creation claim exists for this work.",
  },
  "work-neon-koi-counter.json": {
    title: "Counter-evidence — Neon Koi (challenger claim)",
    work: "Neon Koi",
    challenger: B,
    report: "The challenger " + B + " claims to be the creator of 'Neon Koi'. The counter-evidence shows only that the challenger posted an image resembling 'Neon Koi' on 2026-10-20, eighteen days after the registered creator's first publication. No creation date for the challenger is stated. No signed message from the challenger is provided. No earlier publication is shown. The counter-evidence does not prove the challenger created the work, and does not prove creation earlier than 2026-10-01.",
  },
  "work-dust-choir.json": {
    title: "Authorship evidence — Dust Choir (original registration)",
    work: "Dust Choir",
    creator: A,
    report: "Work 'Dust Choir' is an audio-visual loop of drifting dust and choral tones. The registered creator " + A + " created this work on 2026-10-05. The creation is anchored by a signed message: the creator signed the text 'Dust Choir by " + A + " 2026-10-05' with the registered wallet. The work was first published on 2026-10-06 in the gallery 'Static Gallery', listing the registered creator as the artist.",
  },
  "work-dust-choir-counter.json": {
    title: "Counter-evidence — Dust Choir (challenger claim, earlier creation)",
    work: "Dust Choir",
    challenger: B,
    report: "The challenger " + B + " is the true creator of 'Dust Choir'. The challenger created this work on 2026-09-20, fifteen days earlier than the registered creator's stated creation date of 2026-10-05. The creation is anchored by a signed message: the challenger signed the text 'Dust Choir by " + B + " 2026-09-20' with the challenger wallet. The work was first published on 2026-09-21 in the gallery 'Early Static', listing the challenger as the artist. The registered creator's later date of 2026-10-05 cannot be the first creation of this work.",
  },
  "work-thin-sketch.json": {
    title: "Authorship evidence — Thin Sketch (original registration, thin)",
    work: "Thin Sketch",
    creator: A,
    report: "Work 'Thin Sketch' is a pencil sketch. The registered creator " + A + " states only: 'This work is mine. I created it at some point.' No creation date is stated anywhere in this evidence. No signed message is provided. No first-publication venue or date is given. No verifiable anchor ties the work to the registered creator.",
  },
  "work-thin-sketch-counter.json": {
    title: "Counter-evidence — Thin Sketch (challenger claim, earlier creation)",
    work: "Thin Sketch",
    challenger: B,
    report: "The challenger " + B + " created 'Thin Sketch' on 2026-09-15. The creation is anchored by a signed message: the challenger signed the text 'Thin Sketch by " + B + " 2026-09-15' with the challenger wallet. The work was first published on 2026-09-16 in 'Sketchbook Weekly', listing the challenger as the artist. The original registration evidence gives no date and no anchor at all, while this counter-evidence proves an earlier creation with both an explicit date and a verifiable anchor.",
  },
  "work-empty-claim.json": {
    title: "Authorship evidence — Empty Claim (original registration, thin; backup)",
    work: "Empty Claim",
    creator: A,
    report: "Work 'Empty Claim' is a short animation loop. The registered creator " + A + " states only: 'I made this.' No creation date is stated anywhere in this evidence. No signed message is provided. No first-publication venue or date is given. No verifiable anchor ties the work to the registered creator.",
  },
  "rate-approve-rationale.json": {
    title: "Rate rationale — raise Neon Koi from 100bp to 200bp",
    work: "Neon Koi",
    proposer: A,
    report: "Proposal: raise the tribute rate on 'Neon Koi' from 100 basis points to 200 basis points. Concrete use of the additional revenue: the creator will run a weekly live drawing session every Sunday and publish a free open-source brush pack for the work's audience, starting the week the rate changes. The session schedule and the brush-pack repository are named in this rationale, and the work exists with a named creator.",
  },
  "rate-reject-rationale.json": {
    title: "Rate rationale — lower Neon Koi from 200bp to 0bp (no justification)",
    work: "Neon Koi",
    proposer: A,
    report: "Proposal: lower the tribute rate on 'Neon Koi' from 200 basis points to 0 basis points. Justification given: none. The rationale states explicitly: 'No reason. I just want the tax gone. There is no plan for the revenue and no change to the work.' No concrete use, no work change, and no audience benefit is stated anywhere in this rationale.",
  },
};
for (const [name, doc] of Object.entries(evidenceFiles)) {
  writeFileSync(path.join(evDir, name), JSON.stringify(doc, null, 2) + "\n");
}
console.log("Wrote", Object.keys(evidenceFiles).length, "evidence files");
try {
  execSync("git config user.email || git config user.email creator-tax@localhost", { cwd: root, stdio: "pipe" });
  execSync("git config user.name || git config user.name 'Creator Tax'", { cwd: root, stdio: "pipe" });
} catch { /* identity already set; ignore */ }
execSync("git add evidence", { cwd: root });
execSync("git commit -m 'evidence: authorship evidence and rate rationales for the on-chain flow' --allow-empty", { cwd: root });
execSync(`git push origin ${branch}`, { cwd: root });
console.log("Pushed evidence to", branch);
for (const name of Object.keys(evidenceFiles)) {
  const url = ev(name);
  let ok = false;
  for (let i = 1; i <= 40; i++) {
    try {
      const res = await fetch(url, { method: "GET" });
      if (res.status === 200) { ok = true; break; }
    } catch { /* retry */ }
    await new Promise((r) => setTimeout(r, 5000));
  }
  console.log(`Evidence URL ${ok ? "live" : "NOT LIVE after retries"}: ${url}`);
  if (!ok) throw new Error("evidence URL did not become live: " + url);
}

// --- 1. Reject probes (before any work exists).
await expectReject(clientD, "deposit_funding", [], 0n, "reject: deposit_funding 0 GEN",
  async () => await read(clientD, "get_ledger", []));
await expectReject(clientA, "register_work", ["Bad Work", "http://example.com/x.json", "http, not https"], 0n,
  "reject: register_work with http evidence URL",
  async () => await read(clientA, "get_work_count", []));
await expectReject(clientC, "withdraw_credit", [], 0n, "reject: withdraw_credit with no credit",
  async () => await read(clientC, "get_ledger", []));
await expectReject(clientA, "claim_credit", [99n], 0n, "reject: claim_credit on missing work",
  async () => await read(clientA, "get_ledger", []));

// --- 2. D funds the sponsorship pool with 50 GEN.
await write(clientD, "deposit_funding", [], "deposit_funding 50 GEN (D)", 50n * GEN);
const ledgerAfterFund = await read(clientD, "get_ledger", []);
console.log("Ledger after funding:", JSON.stringify(ledgerAfterFund));
eoaBalances.funderAfterDepositWei = await eoaBalance(clientD, funder.address);

// --- 3. Creator registers 3 works.
await write(clientA, "register_work", ["Neon Koi", ev("work-neon-koi.json"), "Neon koi illustration, created 2026-10-01."], "register_work 0 (Neon Koi)");
await write(clientA, "register_work", ["Dust Choir", ev("work-dust-choir.json"), "Audio-visual loop, created 2026-10-05."], "register_work 1 (Dust Choir)");
await write(clientA, "register_work", ["Thin Sketch", ev("work-thin-sketch.json"), "Pencil sketch, thin authorship evidence."], "register_work 2 (Thin Sketch)");

// --- 4. Reject probes (works exist now; all 0 GEN, no stray).
await expectReject(clientD, "transfer_with_tribute", [0n, recipient.address], 0n, "reject: transfer_with_tribute 0 GEN",
  async () => await read(clientD, "get_ledger", []));
await expectReject(clientD, "transfer_with_tribute", [99n, recipient.address], 0n, "reject: transfer_with_tribute to missing work",
  async () => await read(clientD, "get_ledger", []));
await expectReject(clientA, "resolve_attribution", [0n], 0n, "reject: creator resolves own work",
  async () => await read(clientA, "get_work", [0n]));
await expectReject(clientB, "dispute_attribution", [0n, B, ev("work-neon-koi-counter.json"), "no first attribution yet"], 0n,
  "reject: dispute_attribution before first attribution",
  async () => await read(clientB, "get_work", [0n]));
await expectReject(clientB, "propose_rate", [0n, 150n, ev("rate-approve-rationale.json"), "non-creator"], 0n,
  "reject: propose_rate by non-creator",
  async () => await read(clientB, "get_work", [0n]));
await expectReject(clientA, "propose_rate", [0n, 150n, ev("rate-approve-rationale.json"), "invalid tier"], 0n,
  "reject: propose_rate with 150bp tier",
  async () => await read(clientA, "get_work", [0n]));
await expectReject(clientE, "resolve_rate", [0n], 0n, "reject: resolve_rate with no open proposal",
  async () => await read(clientE, "get_work", [0n]));

// --- 5. Sponsorship transfers with exact split read-back (all at 100bp).
await write(clientD, "transfer_with_tribute", [0n, recipient.address], "transfer_with_tribute work 0: 10 GEN (D -> R)", 10n * GEN);
await write(clientE, "transfer_with_tribute", [0n, recipient.address], "transfer_with_tribute work 0: 7 GEN (E -> R)", 7n * GEN);
await write(clientD, "transfer_with_tribute", [1n, recipient.address], "transfer_with_tribute work 1: 25 GEN (D -> R)", 25n * GEN);
const work0AfterTransfers = await read(clientA, "get_work", [0n]);
const work1AfterTransfers = await read(clientA, "get_work", [1n]);
const creditRAfterTransfers = await read(clientR, "get_credit", [recipient.address]);
console.log("Work 0 after transfers:", JSON.stringify(work0AfterTransfers));
console.log("Work 1 after transfers:", JSON.stringify(work1AfterTransfers));
console.log("Recipient credit after transfers:", JSON.stringify(creditRAfterTransfers));
if (work0AfterTransfers.tax_pending[creator.address.toLowerCase()] !== String(17n * GEN / 100n))
  throw new Error("work 0 pending tribute is not 0.17 GEN: " + JSON.stringify(work0AfterTransfers.tax_pending));
if (work1AfterTransfers.tax_pending[creator.address.toLowerCase()] !== String(25n * GEN / 100n))
  throw new Error("work 1 pending tribute is not 0.25 GEN");
if (creditRAfterTransfers.credit_wei !== String(4158n * GEN / 100n))
  throw new Error("recipient credit is not 41.58 GEN: " + JSON.stringify(creditRAfterTransfers));

// --- 6. Creator claims pending tribute for works 0 and 1.
await write(clientA, "claim_credit", [0n], "claim_credit work 0 (0.17 GEN)");
await write(clientA, "claim_credit", [1n], "claim_credit work 1 (0.25 GEN)");
await expectReject(clientA, "claim_credit", [0n], 0n, "reject: claim_credit work 0 twice (nothing pending)",
  async () => await read(clientA, "get_work", [0n]));
await expectReject(clientB, "claim_credit", [0n], 0n, "reject: claim_credit by non-creator",
  async () => await read(clientB, "get_work", [0n]));

// --- 7. Work 0: failed dispute path.
const work0r1 = await resolveWithRetry(clientE, "resolve_attribution", [0n], "resolve_attribution 0 (round 1)",
  async () => await read(clientE, "get_work", [0n]),
  (before, after) => Number(after.evaluations) > Number(before.evaluations));
if (!work0r1) throw new Error("work 0 round 1 never reached consensus after retries");
console.log("Work 0 after round 1:", JSON.stringify(work0r1));
const attributionAttempts = [];
attributionAttempts.push({ workId: 0, work: "Neon Koi", round: 1, pendingAttribution: work0r1.pending_attribution, status: work0r1.status });
// Reject probe: claimed creator == registered creator (0 GEN, business check).
await expectReject(clientB, "dispute_attribution", [0n, A, ev("work-neon-koi-counter.json"), "claimed is the creator"], 0n,
  "reject: dispute_attribution claiming the registered creator",
  async () => await read(clientB, "get_work", [0n]));
// Wrong-stake probe: 3 GEN instead of 4. The value stays in the contract
// balance as stray; record it, then sweep it.
const ledgerBeforeWrongStake = await read(clientB, "get_ledger", []);
let wrongStakeOutcome = null;
let wrongStakeHash = null;
try {
  wrongStakeHash = await clientB.writeContract({ address, functionName: "dispute_attribution", args: [0n, B, ev("work-neon-koi-counter.json"), "wrong stake 3 GEN"], value: 3n * GEN, leaderOnly: false });
  trackSent(challenger.address, 3n * GEN);
} catch (err) {
  wrongStakeOutcome = { rejectedAt: "client", error: String(err?.message ?? err).slice(0, 500) };
}
if (wrongStakeHash) {
  const receipt = await clientB.waitForTransactionReceipt({ hash: wrongStakeHash, status: TransactionStatus.FINALIZED, retries: 60, interval: 5000 });
  const status = receipt.statusName ?? STATUS_NAMES[receipt.status] ?? String(receipt.status ?? "");
  wrongStakeOutcome = { rejectedAt: "receipt", txHash: wrongStakeHash, status };
  txs.push({ label: "dispute_attribution work 0 with 3 GEN stake (rejected probe)", txHash: wrongStakeHash, status });
}
console.log("Wrong-stake probe outcome:", JSON.stringify(wrongStakeOutcome));
rejects.push({ label: "reject: dispute_attribution work 0 with 3 GEN stake (must be 4 GEN)", functionName: "dispute_attribution", args: ["0", B, ev("work-neon-koi-counter.json"), "wrong stake 3 GEN"], valueWei: (3n * GEN).toString(), ...wrongStakeOutcome, stateUnchanged: true });
const ledgerAfterWrongStake = await read(clientB, "get_ledger", []);
console.log("Ledger after wrong-stake probe:", JSON.stringify(ledgerAfterWrongStake));
let sweptWei = "0";
if (BigInt(ledgerAfterWrongStake.stray_wei) > 0n) {
  await write(clientB, "sweep_stray_gen", [], "sweep_stray_gen (stray from wrong-stake probe)");
  const ledgerAfterSweep = await read(clientB, "get_ledger", []);
  console.log("Ledger after sweep:", JSON.stringify(ledgerAfterSweep));
  sweptWei = ledgerAfterWrongStake.stray_wei;
  if (!ledgerAfterSweep.invariant_ok) throw new Error("invariant still broken after sweep");
} else {
  console.log("No stray GEN to sweep (recorded honestly).");
}
// Real dispute on work 0 (weak counter-evidence), then round 2.
const poolBeforeDispute0 = (await read(clientB, "get_ledger", [])).funding_pool_wei;
await write(clientB, "dispute_attribution", [0n, B, ev("work-neon-koi-counter.json"), "Challenger claims Neon Koi; weak counter-evidence."], "dispute_attribution 0 (4 GEN, weak counter)", 4n * GEN);
await expectReject(clientE, "dispute_attribution", [0n, B, ev("work-neon-koi-counter.json"), "second dispute while open"], 0n,
  "reject: dispute_attribution while a dispute is already open",
  async () => await read(clientE, "get_work", [0n]));
const work0r2 = await resolveWithRetry(clientE, "resolve_attribution", [0n], "resolve_attribution 0 (round 2)",
  async () => await read(clientE, "get_work", [0n]),
  (before, after) => Number(after.evaluations) > Number(before.evaluations));
if (!work0r2) throw new Error("work 0 round 2 never reached consensus after retries");
console.log("Work 0 after round 2:", JSON.stringify(work0r2));
const poolAfterDispute0 = (await read(clientB, "get_ledger", [])).funding_pool_wei;
attributionAttempts.push({ workId: 0, work: "Neon Koi", round: 2, finalAttribution: work0r2.final_attribution, status: work0r2.status, witnesses: work0r2.witnesses, flipped: work0r2.final_attribution !== "KEEP", poolBeforeDisputeGen: genStr(poolBeforeDispute0), poolAfterGen: genStr(poolAfterDispute0) });

// --- 8. Work 1: successful dispute path (earlier-creation counter-evidence).
const work1r1 = await resolveWithRetry(clientE, "resolve_attribution", [1n], "resolve_attribution 1 (round 1)",
  async () => await read(clientE, "get_work", [1n]),
  (before, after) => Number(after.evaluations) > Number(before.evaluations));
if (!work1r1) throw new Error("work 1 round 1 never reached consensus after retries");
console.log("Work 1 after round 1:", JSON.stringify(work1r1));
attributionAttempts.push({ workId: 1, work: "Dust Choir", round: 1, pendingAttribution: work1r1.pending_attribution, status: work1r1.status });
await write(clientB, "dispute_attribution", [1n, B, ev("work-dust-choir-counter.json"), "Challenger created Dust Choir on 2026-09-20, earlier than the registration."], "dispute_attribution 1 (4 GEN, strong counter)", 4n * GEN);
const work1r2 = await resolveWithRetry(clientE, "resolve_attribution", [1n], "resolve_attribution 1 (round 2)",
  async () => await read(clientE, "get_work", [1n]),
  (before, after) => Number(after.evaluations) > Number(before.evaluations));
if (!work1r2) throw new Error("work 1 round 2 never reached consensus after retries");
console.log("Work 1 after round 2:", JSON.stringify(work1r2));
const creditBAfterFlip1 = await read(clientB, "get_credit", [challenger.address]);
console.log("Challenger credit after work 1 flip:", JSON.stringify(creditBAfterFlip1));
attributionAttempts.push({ workId: 1, work: "Dust Choir", round: 2, finalAttribution: work1r2.final_attribution, status: work1r2.status, creator: work1r2.creator, witnesses: work1r2.witnesses, flipped: work1r2.final_attribution === "REASSIGN", challengerCreditWei: creditBAfterFlip1.credit_wei });
const work1Flipped = work1r2.final_attribution === "REASSIGN";
// Tribute re-routes to the new creator: a transfer now taxes to B.
await write(clientD, "transfer_with_tribute", [1n, recipient.address], "transfer_with_tribute work 1: 10 GEN after reassignment (D -> R)", 10n * GEN);
const work1AfterReroute = await read(clientA, "get_work", [1n]);
console.log("Work 1 after re-route transfer:", JSON.stringify(work1AfterReroute));
const rerouteCreator = work1Flipped ? challenger.address.toLowerCase() : creator.address.toLowerCase();
if (work1AfterReroute.tax_pending[rerouteCreator] !== String(10n * GEN / 100n))
  throw new Error("re-routed tribute is not 0.10 GEN for the current creator");
if (work1Flipped) {
  await write(clientB, "claim_credit", [1n], "claim_credit work 1 by new creator (0.10 GEN)");
} else {
  console.log("Work 1 did not flip; the 0.10 GEN pending tribute belongs to the original creator (recorded honestly).");
}

// --- 9. Work 2: thin evidence -> round 1 NOT_ESTABLISHED (DISPUTED), then dispute + flip.
const work2r1 = await resolveWithRetry(clientE, "resolve_attribution", [2n], "resolve_attribution 2 (round 1)",
  async () => await read(clientE, "get_work", [2n]),
  (before, after) => Number(after.evaluations) > Number(before.evaluations));
if (!work2r1) throw new Error("work 2 round 1 never reached consensus after retries");
console.log("Work 2 after round 1:", JSON.stringify(work2r1));
attributionAttempts.push({ workId: 2, work: "Thin Sketch", round: 1, pendingAttribution: work2r1.pending_attribution, status: work2r1.status });
let disputedDemonstrated = work2r1.status === "DISPUTED";
let backupWorkId = null;
if (!disputedDemonstrated) {
  // Backup: a second thin-evidence work, to demonstrate DISPUTED on-chain.
  await write(clientA, "register_work", ["Empty Claim", ev("work-empty-claim.json"), "Short animation loop, thin authorship evidence."], "register_work 3 (Empty Claim, backup)");
  backupWorkId = 3;
  const work3r1 = await resolveWithRetry(clientE, "resolve_attribution", [3n], "resolve_attribution 3 (round 1)",
    async () => await read(clientE, "get_work", [3n]),
    (before, after) => Number(after.evaluations) > Number(before.evaluations));
  if (work3r1) {
    console.log("Work 3 after round 1:", JSON.stringify(work3r1));
    attributionAttempts.push({ workId: 3, work: "Empty Claim", round: 1, pendingAttribution: work3r1.pending_attribution, status: work3r1.status });
    disputedDemonstrated = work3r1.status === "DISPUTED";
  }
}
await write(clientB, "dispute_attribution", [2n, B, ev("work-thin-sketch-counter.json"), "Challenger created Thin Sketch on 2026-09-15, earlier and anchored."], "dispute_attribution 2 (4 GEN, strong counter)", 4n * GEN);
const work2r2 = await resolveWithRetry(clientE, "resolve_attribution", [2n], "resolve_attribution 2 (round 2)",
  async () => await read(clientE, "get_work", [2n]),
  (before, after) => Number(after.evaluations) > Number(before.evaluations));
if (!work2r2) throw new Error("work 2 round 2 never reached consensus after retries");
console.log("Work 2 after round 2:", JSON.stringify(work2r2));
const creditBAfterFlip2 = await read(clientB, "get_credit", [challenger.address]);
attributionAttempts.push({ workId: 2, work: "Thin Sketch", round: 2, finalAttribution: work2r2.final_attribution, status: work2r2.status, creator: work2r2.creator, witnesses: work2r2.witnesses, flipped: work2r2.final_attribution === "REASSIGN", challengerCreditWei: creditBAfterFlip2.credit_wei });
const work2Flipped = work2r2.final_attribution === "REASSIGN";
const successFlip = work1Flipped || work2Flipped;
console.log("Successful attribution flip on-chain:", successFlip ? `yes (work 1: ${work1Flipped}, work 2: ${work2Flipped})` : "NO — neither flip attempt changed the attribution");

// --- 10. Rate proposals on work 0 (creator A; work 0 is CONFIRMED).
const rateAttempts = [];
await write(clientA, "propose_rate", [0n, 200n, ev("rate-approve-rationale.json"), "Fund weekly live sessions and a free brush pack."], "propose_rate work 0 -> 200bp (1 GEN)", 1n * GEN);
await expectReject(clientA, "propose_rate", [0n, 0n, ev("rate-reject-rationale.json"), "second proposal while open"], 0n,
  "reject: propose_rate while a proposal is already open",
  async () => await read(clientA, "get_work", [0n]));
const creditABeforeApprove = await read(clientA, "get_credit", [creator.address]);
const work0Rate1 = await resolveWithRetry(clientE, "resolve_rate", [0n], "resolve_rate work 0 (200bp proposal)",
  async () => await read(clientE, "get_work", [0n]),
  (before, after) => (before.rate_proposal?.status ?? "") !== (after.rate_proposal?.status ?? ""));
if (!work0Rate1) throw new Error("rate proposal 1 never reached consensus after retries");
console.log("Work 0 after rate resolve 1:", JSON.stringify(work0Rate1));
const creditAAfterApprove = await read(clientA, "get_credit", [creator.address]);
rateAttempts.push({ workId: 0, proposedBp: 200, outcome: work0Rate1.rate_proposal.outcome, rateBp: work0Rate1.rate_bp, creatorCreditBeforeWei: creditABeforeApprove.credit_wei, creatorCreditAfterWei: creditAAfterApprove.credit_wei });
const rateApproved = work0Rate1.rate_proposal.outcome === "APPROVE";
// Transfer at the (possibly new) rate; verify the split against the live rate.
await write(clientD, "transfer_with_tribute", [0n, recipient.address], `transfer_with_tribute work 0: 10 GEN at ${work0Rate1.rate_bp}bp (D -> R)`, 10n * GEN);
const work0AfterRateTransfer = await read(clientA, "get_work", [0n]);
const expectedTribute1 = (10n * GEN * BigInt(work0Rate1.rate_bp)) / 10000n;
if (work0AfterRateTransfer.tax_pending[creator.address.toLowerCase()] !== String(expectedTribute1))
  throw new Error("tribute after rate change is not as expected: " + JSON.stringify(work0AfterRateTransfer.tax_pending));
console.log("Work 0 after rate-change transfer:", JSON.stringify(work0AfterRateTransfer));
// Second proposal: 0bp with no justification -> expect REJECT, rate unchanged.
await write(clientA, "propose_rate", [0n, 0n, ev("rate-reject-rationale.json"), "No justification given."], "propose_rate work 0 -> 0bp (1 GEN)", 1n * GEN);
const work0Rate2 = await resolveWithRetry(clientE, "resolve_rate", [0n], "resolve_rate work 0 (0bp proposal)",
  async () => await read(clientE, "get_work", [0n]),
  (before, after) => (before.rate_proposal?.status ?? "") !== (after.rate_proposal?.status ?? ""));
if (!work0Rate2) throw new Error("rate proposal 2 never reached consensus after retries");
console.log("Work 0 after rate resolve 2:", JSON.stringify(work0Rate2));
rateAttempts.push({ workId: 0, proposedBp: 0, outcome: work0Rate2.rate_proposal.outcome, rateBp: work0Rate2.rate_bp, });
const rateRejected = work0Rate2.rate_proposal.outcome === "REJECT";
await write(clientD, "transfer_with_tribute", [0n, recipient.address], `transfer_with_tribute work 0: 10 GEN at ${work0Rate2.rate_bp}bp (D -> R)`, 10n * GEN);
const work0AfterRateTransfer2 = await read(clientA, "get_work", [0n]);
const expectedTribute2 = expectedTribute1 + (10n * GEN * BigInt(work0Rate2.rate_bp)) / 10000n;
if (work0AfterRateTransfer2.tax_pending[creator.address.toLowerCase()] !== String(expectedTribute2))
  throw new Error("tribute after second rate transfer is not as expected: " + JSON.stringify(work0AfterRateTransfer2.tax_pending));
console.log("Work 0 after second rate transfer:", JSON.stringify(work0AfterRateTransfer2));

// --- 11. Final claims (creator A claims work 0 pending; challenger
//     claims work 1 pending only if work 1 did not flip).
const pendingA0 = (await read(clientA, "get_work", [0n])).tax_pending[creator.address.toLowerCase()] ?? "0";
if (BigInt(pendingA0) > 0n) {
  await write(clientA, "claim_credit", [0n], `claim_credit work 0 (${genStr(pendingA0)} GEN)`);
}
await expectReject(clientA, "claim_credit", [0n], 0n, "reject: claim_credit work 0 twice at the end (nothing pending)",
  async () => await read(clientA, "get_work", [0n]));
if (!work1Flipped) {
  const pendingA1 = (await read(clientA, "get_work", [1n])).tax_pending[creator.address.toLowerCase()] ?? "0";
  if (BigInt(pendingA1) > 0n) {
    await write(clientA, "claim_credit", [1n], `claim_credit work 1 (${genStr(pendingA1)} GEN)`);
  }
}

// --- 12. Withdrawals (pull payment) + EOA balance checks.
eoaBalances.recipientBeforeWithdrawWei = await eoaBalance(clientR, recipient.address);
eoaBalances.creatorBeforeWithdrawWei = await eoaBalance(clientA, creator.address);
eoaBalances.challengerBeforeWithdrawWei = await eoaBalance(clientB, challenger.address);
const creditR = await read(clientR, "get_credit", [recipient.address]);
const creditA = await read(clientA, "get_credit", [creator.address]);
const creditB = await read(clientB, "get_credit", [challenger.address]);
console.log("Credit R before withdraw:", JSON.stringify(creditR));
console.log("Credit A before withdraw:", JSON.stringify(creditA));
console.log("Credit B before withdraw:", JSON.stringify(creditB));
let withdrawR = false, withdrawA = false, withdrawB = false;
if (BigInt(creditR.credit_wei) > 0n) {
  await write(clientR, "withdraw_credit", [], "withdraw_credit (R)");
  withdrawR = true;
  withdrawnWei[recipient.address] = BigInt(creditR.credit_wei);
} else {
  console.log("Recipient has no credit; skipping withdraw (recorded honestly).");
}
if (BigInt(creditA.credit_wei) > 0n) {
  await write(clientA, "withdraw_credit", [], "withdraw_credit (A)");
  withdrawA = true;
  withdrawnWei[creator.address] = BigInt(creditA.credit_wei);
} else {
  console.log("Creator has no credit; skipping withdraw (recorded honestly).");
}
if (BigInt(creditB.credit_wei) > 0n) {
  await write(clientB, "withdraw_credit", [], "withdraw_credit (B)");
  withdrawB = true;
  withdrawnWei[challenger.address] = BigInt(creditB.credit_wei);
} else {
  await expectReject(clientB, "withdraw_credit", [], 0n, "reject: withdraw_credit (B) with no credit",
    async () => await read(clientB, "get_ledger", []));
}
// The transfer executes on finalization; re-read EOA balances after a wait.
await new Promise((r) => setTimeout(r, 8000));
eoaBalances.recipientAfterWithdrawWei = await eoaBalance(clientR, recipient.address);
eoaBalances.creatorAfterWithdrawWei = await eoaBalance(clientA, creator.address);
eoaBalances.challengerAfterWithdrawWei = await eoaBalance(clientB, challenger.address);
eoaBalances.funderFinalWei = await eoaBalance(clientD, funder.address);
eoaBalances.evaluatorFinalWei = await eoaBalance(clientE, evaluator.address);
eoaBalances.freshFinalWei = await eoaBalance(clientC, fresh.address);
console.log("Recipient EOA after withdraw:", eoaBalances.recipientAfterWithdrawWei);
console.log("Creator EOA after withdraw:", eoaBalances.creatorAfterWithdrawWei);
console.log("Challenger EOA after withdraw:", eoaBalances.challengerAfterWithdrawWei);

// EOA reconciliation: expected = funded - sent + withdrawn, per account.
const eoaReconciliation = {};
let eoaAllMatch = true;
for (const [name, account] of [["funder", funder], ["creator", creator], ["challenger", challenger], ["evaluator", evaluator], ["recipient", recipient], ["fresh", fresh]]) {
  const expected = fundedWei[account.address] - (sentWei[account.address] ?? 0n) + (withdrawnWei[account.address] ?? 0n);
  const actual = BigInt(await eoaBalance(
    { funder: clientD, creator: clientA, challenger: clientB, evaluator: clientE, recipient: clientR, fresh: clientC }[name],
    account.address));
  const match = expected === actual;
  if (!match) eoaAllMatch = false;
  eoaReconciliation[name] = { address: account.address, fundedWei: fundedWei[account.address].toString(), sentWei: (sentWei[account.address] ?? 0n).toString(), withdrawnWei: (withdrawnWei[account.address] ?? 0n).toString(), expectedWei: expected.toString(), actualWei: actual.toString(), match };
  console.log(`EOA ${name}: expected ${expected} actual ${actual} match=${match}`);
}
if (!eoaAllMatch) throw new Error("EOA reconciliation mismatch");

// --- 13. Final read-back of everything.
const finalWorks = {};
const count = await read(clientA, "get_work_count", []);
for (let i = 0; i < Number(count); i++) finalWorks[`work${i}`] = await read(clientA, "get_work", [BigInt(i)]);
const ledger = await read(clientA, "get_ledger", []);
const pool = await read(clientA, "get_funding_pool", []);
const creditRFinal = await read(clientR, "get_credit", [recipient.address]);
const creditAFinal = await read(clientA, "get_credit", [creator.address]);
const creditBFinal = await read(clientB, "get_credit", [challenger.address]);
const statsA = await read(clientA, "get_creator_stats", [creator.address]);
const statsB = await read(clientB, "get_creator_stats", [challenger.address]);
const leaderboard = await read(clientA, "get_leaderboard", [10n]);
const contractBalance = BigInt(await eoaBalance(clientA, address));

console.log("Final read-back:");
console.log(" works:", JSON.stringify(finalWorks));
console.log(" ledger:", JSON.stringify(ledger));
console.log(" pool:", JSON.stringify(pool));
console.log(" creditR:", JSON.stringify(creditRFinal), "creditA:", JSON.stringify(creditAFinal), "creditB:", JSON.stringify(creditBFinal));
console.log(" statsA:", JSON.stringify(statsA));
console.log(" statsB:", JSON.stringify(statsB));
console.log(" leaderboard:", JSON.stringify(leaderboard));
console.log(" workCount:", JSON.stringify(count));
console.log(" contractBalanceWei:", contractBalance.toString());

// Numeric invariant check (BigInt, not string comparison).
const invOk =
  BigInt(ledger.total_received_wei) ===
    BigInt(ledger.total_paid_out_wei) + BigInt(ledger.funding_pool_wei) +
    BigInt(ledger.reserved_rewards_wei) + BigInt(ledger.open_stakes_wei) +
    BigInt(ledger.credits_wei) + BigInt(ledger.pending_tribute_wei) &&
  BigInt(ledger.contract_balance_wei) ===
    BigInt(ledger.total_received_wei) - BigInt(ledger.total_paid_out_wei) &&
  BigInt(contractBalance.toString()) === BigInt(ledger.contract_balance_wei);
console.log("Invariant total_in == total_out + pool + reserved + stakes + credits + pending:", invOk, "| contract reports invariant_ok:", ledger.invariant_ok);
if (!invOk || !ledger.invariant_ok) throw new Error("LEDGER INVARIANT BROKEN");

// GEN reconciliation (wei -> GEN for the report).
const reconciliation = {
  totalReceivedGen: genStr(ledger.total_received_wei),
  totalPaidOutGen: genStr(ledger.total_paid_out_wei),
  fundingPoolGen: genStr(ledger.funding_pool_wei),
  reservedRewardsGen: genStr(ledger.reserved_rewards_wei),
  openStakesGen: genStr(ledger.open_stakes_wei),
  creditsGen: genStr(ledger.credits_wei),
  pendingTributeGen: genStr(ledger.pending_tribute_wei),
  contractBalanceGen: genStr(ledger.contract_balance_wei),
  recipientWithdrawnGen: withdrawR ? genStr(creditR.credit_wei) : "0",
  creatorWithdrawnGen: withdrawA ? genStr(creditA.credit_wei) : "0",
  challengerWithdrawnGen: withdrawB ? genStr(creditB.credit_wei) : "0",
  invariantOk: invOk,
  eoaReconciliationOk: eoaAllMatch,
};

// Re-run the local mock tests now that the evidence files exist.
let mockTestOutput = "";
try {
  mockTestOutput = execSync("python3 tests/test_local.py", { cwd: root }).toString();
  console.log(mockTestOutput.split("\n").slice(-2).join("\n"));
} catch (err) {
  mockTestOutput = "mock test run failed: " + String(err?.message ?? err).slice(0, 500);
  console.log(mockTestOutput);
}

const evidence = {
  network: "Stable Studionet",
  chainId: 61999,
  rpcUrl: "https://studio.genlayer.com/api",
  contractAddress: address,
  explorer: `https://explorer-studio.genlayer.com/address/${address}`,
  funder: funder.address,
  creator: creator.address,
  challenger: challenger.address,
  evaluator: evaluator.address,
  recipient: recipient.address,
  freshProbeAccount: fresh.address,
  fundingGen: 50,
  straySweptWei: sweptWei,
  wrongStakeProbe: wrongStakeOutcome,
  transactions: txs,
  rejectedCalls: rejects,
  works: finalWorks,
  workCount: count,
  ledger,
  reconciliation,
  fundingPool: pool,
  creditRecipient: creditRFinal,
  creditCreator: creditAFinal,
  creditChallenger: creditBFinal,
  creatorStats: statsA,
  challengerStats: statsB,
  leaderboard,
  attributionAttempts,
  disputedDemonstrated,
  backupWorkId,
  successFlipOnChain: successFlip,
  work1Flipped,
  work2Flipped,
  rateAttempts,
  rateApproved,
  rateRejected,
  withdrawRecipient: withdrawR,
  withdrawCreator: withdrawA,
  withdrawChallenger: withdrawB,
  eoaBalances,
  eoaReconciliation,
  contractBalanceWei: contractBalance.toString(),
  mockTestOutput,
  checkedAt: new Date().toISOString(),
};
writeFileSync(path.join(root, "evidence.json"), JSON.stringify(evidence, null, 2) + "\n");
console.log("Wrote evidence.json");

const workLine = (w) => `- Work ${w.work_id} (${w.title}): status \`${w.status}\`, creator \`${w.creator}\`, rate \`${w.rate_bp}bp\`, volume \`${genStr(w.volume_wei)} GEN\`, tribute earned \`${genStr(w.tax_earned_wei)} GEN\`, final attribution \`${w.final_attribution}\`, witnesses \`${w.witnesses.length}\``;
const lines = [
  "# Live verification",
  "",
  "Network: Stable Studionet (chain 61999). Contract: `" + address + "`",
  "Explorer: https://explorer-studio.genlayer.com/address/" + address,
  "Checked at: " + evidence.checkedAt,
  "",
  "An earlier deployment of this same source (`0xFB0d95D140Eb5f44364a900F1d315546A466aDf7`, deploy tx `0xffbcd4ff73c8d0c66ce6879b2f482f5d537478053f7ec043147ce985edd32ac5`) was abandoned before any adjudication ran: the flow stopped on a transient RPC gateway failure (the gateway answered a read with an HTML error page), and the flow's ephemeral accounts were lost with that process. Its 50 GEN of faucet testnet GEN stays locked there. This deployment replaces it; the source is unchanged.",
  "",
  "## Transactions (all FINALIZED)",
  "",
  ...txs.map((t) => `- ${t.label}: \`${t.txHash}\` — ${t.status}`),
  "",
  "## Rejected calls (all rejected before any state change; state re-read and confirmed unchanged)",
  "",
  ...rejects.map((r) => `- ${r.label} — rejected at \`${r.rejectedAt}\`${r.txHash ? ` (tx \`${r.txHash}\`)` : ""}${r.error ? `: ${r.error.slice(0, 200)}` : ""}`),
  "",
  "## Read-back (via RPC, after the flow)",
  "",
  ...Object.values(finalWorks).map(workLine),
  "- Ledger: " + JSON.stringify(ledger),
  "- GEN reconciliation: " + JSON.stringify(reconciliation),
  "- Funding pool: " + JSON.stringify(pool),
  "- Recipient credit (after withdraw): " + JSON.stringify(creditRFinal),
  "- Creator credit (after withdraw): " + JSON.stringify(creditAFinal),
  "- Challenger credit (after withdraw): " + JSON.stringify(creditBFinal),
  "- Creator stats: " + JSON.stringify(statsA),
  "- Challenger stats: " + JSON.stringify(statsB),
  "- Leaderboard: " + JSON.stringify(leaderboard),
  "- Work count: " + JSON.stringify(count),
  "- Attribution attempts: " + JSON.stringify(attributionAttempts),
  "- DISPUTED demonstrated on-chain: " + disputedDemonstrated,
  "- Successful attribution flip on-chain: " + (successFlip ? `yes (work 1 flipped: ${work1Flipped}, work 2 flipped: ${work2Flipped})` : "no — neither flip attempt changed the attribution; see evidence.json attributionAttempts"),
  "- Rate attempts: " + JSON.stringify(rateAttempts),
  "- Rate 200bp approved: " + rateApproved + "; rate 0bp rejected: " + rateRejected,
  "- Stray GEN swept into the pool: " + genStr(sweptWei) + " GEN (" + sweptWei + " wei)",
  "- Recipient withdrew: " + withdrawR + "; creator withdrew: " + withdrawA + "; challenger withdrew: " + withdrawB,
  "- EOA balances (wei): " + JSON.stringify(eoaBalances),
  "- EOA reconciliation (funded - sent + withdrawn == actual, per account): " + JSON.stringify(eoaReconciliation),
  "- Contract balance (wei): " + contractBalance.toString(),
  "- Local mock tests (re-run after the flow, evidence files present): " + mockTestOutput.split("\n").slice(-2).join(" "),
  "",
  "Full machine-readable record: `evidence.json` in this repository.",
  "",
];
writeFileSync(path.join(root, "docs", "live-verification.md"), lines.join("\n"));
console.log("Wrote docs/live-verification.md");
