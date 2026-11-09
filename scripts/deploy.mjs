/* Deploy Creator Tax v0.1.0 to Stable Studionet (chain 61999) only.
 *
 * Usage:
 *   node scripts/deploy.mjs
 *
 * The deployer is an ephemeral key generated for this run only; the
 * contract is permissionless, so losing that key loses nothing. No key
 * is ever written to disk or to deployment.json.
 *
 * Steps: fund the ephemeral deployer with 10000 testnet GEN via
 * sim_fundAccount (integer wei as a JS Number; 10000 GEN = 1e22) ->
 * deploy -> wait FINALIZED -> read back gen_getContractCode, base64
 * decode it, and require its SHA-256 to equal the source file's SHA-256.
 * Writes deployment.json (no private key).
 */
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createClient, createAccount, generatePrivateKey } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const codePath = path.join(root, "contracts", "creator_tax.py");
const code = readFileSync(codePath, "utf-8");
const codeSha = createHash("sha256").update(code).digest("hex");
console.log("Source SHA-256:", codeSha);

const account = createAccount(generatePrivateKey());
console.log("Deployer (ephemeral):", account.address);
console.log("Network: Stable Studionet, chain 61999, https://studio.genlayer.com/api");

let sourceCommit = "";
try {
  sourceCommit = execSync("git rev-parse HEAD", { cwd: root }).toString().trim();
} catch {
  sourceCommit = "";
}
console.log("Source commit:", sourceCommit || "(not a git checkout)");

const client = createClient({ chain: studionet, account });

// 1. Fund the deployer with 10000 testnet GEN (faucet-equivalent).
const fundTx = await client.request({
  method: "sim_fundAccount",
  params: [account.address, 10000 * 10 ** 18],
});
console.log("sim_fundAccount tx:", String(fundTx).slice(0, 80));
const eoaBalance = await client.getBalance({ address: account.address });
console.log("Deployer balance (wei):", eoaBalance.toString());
if (eoaBalance.toString() !== (10000n * 10n ** 18n).toString())
  throw new Error("fund amount mismatch");

// 2. Deploy.
const txHash = await client.deployContract({ code, args: [], leaderOnly: false });
console.log("Deploy tx:", txHash);
const receipt = await client.waitForTransactionReceipt({
  hash: txHash,
  status: TransactionStatus.FINALIZED,
  retries: 180,
  interval: 5000,
});
const STATUS = { 0: "UNINITIALIZED", 1: "PENDING", 2: "PROPOSING", 3: "COMMITTING", 4: "REVEALING", 5: "ACCEPTED", 6: "UNDETERMINED", 7: "FINALIZED", 8: "CANCELED" };
const statusName = receipt.statusName ?? STATUS[receipt.status] ?? String(receipt.status ?? "");
console.log("Receipt status:", statusName);
if (statusName !== "FINALIZED") throw new Error("deploy did not FINALIZE: " + statusName);

const address =
  receipt?.data?.contract_address ??
  receipt?.txDataDecoded?.contractAddress ??
  receipt?.contractAddress ??
  null;
if (!address) {
  console.log("Full receipt (no private key):", JSON.stringify(receipt, null, 2).slice(0, 4000));
  throw new Error("Could not find contract address in deploy receipt");
}
console.log("Contract address:", address);

// 3. Verify deployed code: gen_getContractCode returns base64 source.
const cc = await client.request({ method: "gen_getContractCode", params: [address] });
if (typeof cc !== "string" || cc.length === 0) throw new Error("gen_getContractCode returned nothing");
const decoded = Buffer.from(cc, "base64").toString("utf-8");
const deployedSha = createHash("sha256").update(decoded).digest("hex");
console.log("Deployed code SHA-256:", deployedSha, "| match:", deployedSha === codeSha);
if (decoded !== code) throw new Error("deployed code differs from source file byte-for-byte");
if (deployedSha !== codeSha) throw new Error("deployed code SHA mismatch");

const deployment = {
  network: "Stable Studionet",
  chainId: 61999,
  rpcUrl: "https://studio.genlayer.com/api",
  explorer: `https://explorer-studio.genlayer.com/address/${address}`,
  studio: `https://studio.genlayer.com/?import-contract=${address}`,
  contractAddress: address,
  deployTxHash: txHash,
  deployer: account.address,
  fundTxHash: String(fundTx),
  contractFile: "contracts/creator_tax.py",
  contractSha256: codeSha,
  deployedCodeSha256: deployedSha,
  deployedCodeMatchesSource: true,
  sourceCommit,
  deployedAt: new Date().toISOString(),
  receiptStatus: statusName,
};
writeFileSync(path.join(root, "deployment.json"), JSON.stringify(deployment, null, 2) + "\n");
console.log("Wrote deployment.json");
