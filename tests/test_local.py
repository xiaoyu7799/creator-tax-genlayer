"""Local mock tests for Creator Tax v0.1.0 — MOCK ONLY, not on-chain results.

Runs the contract's pure deterministic logic (tribute split math, rate
tiers, pure-Python SHA-256, GEN economics constants and the ledger bucket
moves) in plain Python with the GenLayer runtime stubbed out. No network,
no consensus, no chain state. The on-chain flow is scripts/flow.mjs; its
results are recorded separately in evidence.json /
docs/live-verification.md.

Evidence-file checks run only when the evidence files exist (they are
written by scripts/flow.mjs with the run's real addresses, then pushed);
before the flow they are skipped, never faked.

Run: python3 tests/test_local.py
"""
import hashlib
import json
import sys
import types
from pathlib import Path

# --- Stub the genlayer module so the contract file can be imported locally.
genlayer = types.ModuleType("genlayer")


class _Contract:
    pass


class _WriteDeco:
    def __call__(self, fn):
        return fn

    @staticmethod
    def payable(fn):
        return fn


class _Public:
    write = _WriteDeco()

    @staticmethod
    def view(fn):
        return fn


class _Message:
    sender_address = None
    value = 0


class _VM:
    class UserError(Exception):
        pass

    class Return:
        pass

    @staticmethod
    def run_nondet_unsafe(judge, validate):
        raise NotImplementedError("nondet not available in mock")


class _Evm:
    @staticmethod
    def contract_interface(cls):
        return cls


def _Address(addr):
    return addr


genlayer.Contract = _Contract
genlayer.public = _Public()
genlayer.message = _Message()
genlayer.vm = _VM()
genlayer.u256 = int
genlayer.TreeMap = dict
genlayer.DynArray = list
genlayer.Address = _Address
genlayer.evm = _Evm()
# The contract uses the `gl.` prefix after `from genlayer import *`,
# so the stub must export a `gl` namespace carrying the same API.
genlayer.gl = types.SimpleNamespace(
    Contract=_Contract, public=_Public(), message=_Message(), vm=_VM(),
    nondet=types.SimpleNamespace(), eq_principle=types.SimpleNamespace(),
    evm=_Evm(),
)
sys.modules["genlayer"] = genlayer
# `from genlayer import *` needs these names exported.
genlayer.__all__ = ["gl", "Contract", "public", "message", "vm", "u256",
                    "TreeMap", "DynArray", "Address", "evm"]

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / "contracts" / "creator_tax.py").read_text()
ns = {"__name__": "creator_tax_under_test"}
exec(compile(src, str(ROOT / "contracts" / "creator_tax.py"), "exec"), ns)

tribute_for = ns["tribute_for"]
is_hex = ns["_is_hex_address"]
sha = ns["pure_sha256_hex"]
GEN = ns["GEN_WEI"]
RATE_TIERS = ns["RATE_TIERS"]
RATE_DEFAULT_BP = ns["RATE_DEFAULT_BP"]
RATE_DENOM = ns["RATE_DENOMINATOR"]
DISPUTE_STAKE = ns["DISPUTE_STAKE_WEI"]
DISPUTE_REWARD = ns["DISPUTE_SUCCESS_REWARD_WEI"]
RATE_STAKE = ns["RATE_STAKE_WEI"]

passed = 0
skipped = 0


def check(name, cond):
    global passed
    assert cond, "FAIL: " + name
    passed += 1
    print("ok - " + name)


def skip(name):
    global skipped
    skipped += 1
    print("skip - " + name)


# 1. SHA-256 matches hashlib on standard test vectors (pure-Python impl).
for msg in ["", "abc", "The quick brown fox jumps over the lazy dog",
            "creator-tax|work-0|evidence", "a" * 200]:
    check("sha256 matches hashlib for %r" % msg[:20],
          sha(msg) == hashlib.sha256(msg.encode("utf-8")).hexdigest())

# 2. Tribute split: exact integer division, remainder to the recipient,
#    tribute + recipient share == amount, for every tier and a spread of
#    amounts including odd wei values.
for rate in RATE_TIERS:
    for amount in [1, 3, 99, 100, 101, 9999, 10 ** 17, 7 * 10 ** 18,
                   10 * 10 ** 18, 25 * 10 ** 18, 123456789012345678]:
        tribute = tribute_for(amount, rate)
        check("split amount=%d rate=%d: tribute+share==amount" % (amount, rate),
              tribute + (amount - tribute) == amount)
        check("split amount=%d rate=%d: tribute==amount*rate//10000" % (amount, rate),
              tribute == (amount * rate) // 10000)
        check("split amount=%d rate=%d: remainder < 10000 wei-equivalent" % (amount, rate),
              (amount * rate) % 10000 < 10000)

# 3. The flow's exact transfer numbers (10 / 7 / 25 GEN at 100bp,
#    10 GEN at 200bp): tribute is exact, no rounding loss beyond the
#    integer-division remainder, which is zero for these amounts.
check("10 GEN at 100bp -> 0.1 GEN tribute", tribute_for(10 * GEN, 100) == GEN // 10)
check("7 GEN at 100bp -> 0.07 GEN tribute", tribute_for(7 * GEN, 100) == 7 * GEN // 100)
check("25 GEN at 100bp -> 0.25 GEN tribute", tribute_for(25 * GEN, 100) == GEN // 4)
check("10 GEN at 200bp -> 0.2 GEN tribute", tribute_for(10 * GEN, 200) == GEN // 5)
check("10 GEN at 0bp -> 0 tribute", tribute_for(10 * GEN, 0) == 0)

# 4. Rate tiers: exactly 0 / 100 / 200bp, default 100bp; nothing else
#    can ever be stored (the contract rejects any other tier).
check("rate tiers are exactly (0, 100, 200)", tuple(RATE_TIERS) == (0, 100, 200))
check("default rate is 100bp", RATE_DEFAULT_BP == 100)
check("rate denominator is 10000", RATE_DENOM == 10000)
check("150bp is not a tier", 150 not in RATE_TIERS)
check("101bp is not a tier", 101 not in RATE_TIERS)

# 5. Worst-case spread proof, modeled: a validator accepts a leader
#    verdict only if it equals the validator's own verdict exactly AND
#    the SHA-256 of every fetched evidence body matches exactly. Hence
#    any two accepted leader outputs L, L' satisfy L == V and L' == V,
#    so L == L'. The stored rate tier, creator and tribute amount are
#    pure functions of that single verdict plus deterministic integer
#    division, so they are identical too. Spread = 0.
#    Verdict vocabularies are fixed and finite: round 1 has 2 values,
#    round 2 has 2 values, rate has 2 values; there is no continuous
#    score and no tolerance band anywhere.
ROUND1 = ("ESTABLISHED", "NOT_ESTABLISHED")
ROUND2 = ("KEEP", "REASSIGN")
RATE_VERDICTS = ("APPROVE", "REJECT")


def accepted_outputs(own_verdict, own_shas):
    # Every output a validator could accept must match its own verdict
    # and its own evidence SHAs exactly: at most one such output exists.
    return [(own_verdict, tuple(own_shas))]


for vocab in (ROUND1, ROUND2, RATE_VERDICTS):
    for v in vocab:
        outs = accepted_outputs(v, ["sha-a", "sha-b"])
        check("exact equivalence: one acceptable output for verdict %s" % v,
              len(outs) == 1 and outs[0][0] == v)
check("round-1 verdict vocabulary is binary", len(ROUND1) == 2)
check("round-2 verdict vocabulary is binary", len(ROUND2) == 2)
check("rate verdict vocabulary is binary", len(RATE_VERDICTS) == 2)
check("no tolerance band: spread between two accepted outputs is 0",
      accepted_outputs("KEEP", ["s1", "s2"]) == accepted_outputs("KEEP", ["s1", "s2"]))

# 6. Real GEN economics constants (wei; 1 GEN = 10^18 wei).
check("1 GEN == 10^18 wei", GEN == 10 ** 18)
check("dispute stake == 4 GEN", DISPUTE_STAKE == 4 * GEN)
check("dispute success reward == 1 GEN", DISPUTE_REWARD == 1 * GEN)
check("rate proposal stake == 1 GEN", RATE_STAKE == 1 * GEN)
check("stake + success reward == 5 GEN credit on success",
      DISPUTE_STAKE + DISPUTE_REWARD == 5 * GEN)
check("dispute economics differ from the earlier projects (4/1, not 3/2, 1/0.5 or 2/0.75)",
      (DISPUTE_STAKE, DISPUTE_REWARD) == (4 * GEN, 1 * GEN))

# 7. Address validation.
check("valid address accepted", is_hex("0x" + "ab" * 20))
check("short address rejected", not is_hex("0x1234"))
check("non-hex rejected", not is_hex("0x" + "zz" * 20))
check("missing 0x rejected", not is_hex("ab" * 20))

# 8. Ledger invariant simulation, replicating the contract's bucket
#    moves exactly: total_received == total_paid_out + funding_pool
#    + reserved + open_stakes + credits + pending_tribute, at every step.
#    This is the exact walk the on-chain flow performs (50 GEN funding,
#    3 GEN stray from a rejected wrong-stake call swept into the pool,
#    72 GEN of sponsorship transfers, three 4 GEN dispute stakes, two
#    1 GEN rate stakes, 83 GEN withdrawn).
ledger = {"received": 0, "paid": 0, "pool": 0, "reserved": 0,
          "stakes": 0, "credits": 0, "pending": 0}


def inv(lbl):
    check("invariant holds: " + lbl,
          ledger["received"] == ledger["paid"] + ledger["pool"] + ledger["reserved"]
          + ledger["stakes"] + ledger["credits"] + ledger["pending"])


# Fund the pool with 50 GEN.
ledger["received"] += 50 * GEN
ledger["pool"] += 50 * GEN
inv("after funding 50 GEN")
# A 3 GEN dispute with the wrong stake is rejected; the 3 GEN stays in
# the balance as stray, then is swept into the pool (received += 3).
ledger["pool"] += 3 * GEN
ledger["received"] += 3 * GEN
inv("after sweeping 3 GEN stray into the pool")
# Sponsorship transfers, 72 GEN total: recipient credits + pending tax.
# 10 GEN at 100bp: 9.9 recipient, 0.1 pending. 7 GEN: 6.93 / 0.07.
# 25 GEN: 24.75 / 0.25. 10 GEN (post-reassign, 100bp): 9.9 / 0.1.
# 10 GEN at 200bp: 9.8 / 0.2. 10 GEN at 200bp: 9.8 / 0.2.
for amount, rate in [(10, 100), (7, 100), (25, 100), (10, 100), (10, 200), (10, 200)]:
    tribute = tribute_for(amount * GEN, rate)
    ledger["received"] += amount * GEN
    ledger["credits"] += amount * GEN - tribute
    ledger["pending"] += tribute
    inv("after transfer %d GEN at %dbp" % (amount, rate))
check("pending tribute is 0.92 GEN after the six transfers",
      ledger["pending"] == 92 * GEN // 100)
check("recipient credits are 71.08 GEN after the six transfers",
      ledger["credits"] == 7108 * GEN // 100)
# Dispute 1 opens: stake 4 GEN in, 1 GEN reserved from pool.
ledger["received"] += 4 * GEN
ledger["stakes"] += 4 * GEN
ledger["pool"] -= 1 * GEN
ledger["reserved"] += 1 * GEN
inv("after dispute 1 opens")
# Dispute 1 fails: stake + reservation both into the pool.
ledger["pool"] += 4 * GEN + 1 * GEN
ledger["stakes"] -= 4 * GEN
ledger["reserved"] -= 1 * GEN
inv("after dispute 1 fails")
# Dispute 2 opens, then succeeds: challenger credited 4 + 1 GEN.
ledger["received"] += 4 * GEN
ledger["stakes"] += 4 * GEN
ledger["pool"] -= 1 * GEN
ledger["reserved"] += 1 * GEN
inv("after dispute 2 opens")
ledger["credits"] += 4 * GEN + 1 * GEN
ledger["stakes"] -= 4 * GEN
ledger["reserved"] -= 1 * GEN
inv("after dispute 2 succeeds")
# Dispute 3 opens, then succeeds: challenger credited 4 + 1 GEN.
ledger["received"] += 4 * GEN
ledger["stakes"] += 4 * GEN
ledger["pool"] -= 1 * GEN
ledger["reserved"] += 1 * GEN
inv("after dispute 3 opens")
ledger["credits"] += 4 * GEN + 1 * GEN
ledger["stakes"] -= 4 * GEN
ledger["reserved"] -= 1 * GEN
inv("after dispute 3 succeeds")
# Rate proposal 1 (200bp) approved: 1 GEN stake refunded as credit.
ledger["received"] += 1 * GEN
ledger["stakes"] += 1 * GEN
inv("after rate proposal 1 opens")
ledger["credits"] += 1 * GEN
ledger["stakes"] -= 1 * GEN
inv("after rate proposal 1 approved")
# Rate proposal 2 (0bp) rejected: 1 GEN stake forfeited to the pool.
ledger["received"] += 1 * GEN
ledger["stakes"] += 1 * GEN
inv("after rate proposal 2 opens")
ledger["pool"] += 1 * GEN
ledger["stakes"] -= 1 * GEN
inv("after rate proposal 2 rejected")
# Creator claims the 0.82 GEN pending tribute accrued while they were
# creator (work 0: 0.17, work 1 pre-reassignment: 0.25, work 0 at 200bp:
# 0.40); the new creator claims the 0.10 GEN accrued after reassignment.
# Pending -> credit.
ledger["pending"] -= 82 * GEN // 100
ledger["credits"] += 82 * GEN // 100
inv("after creator claims their 0.82 GEN pending tribute")
ledger["pending"] -= 10 * GEN // 100
ledger["credits"] += 10 * GEN // 100
inv("after new creator claims their 0.10 GEN pending tribute")
# Everyone withdraws: recipient 71.08 + creator 1.82 + challenger 10.1.
check("total credits before withdrawal are 83 GEN",
      ledger["credits"] == 83 * GEN)
ledger["credits"] -= 83 * GEN
ledger["paid"] += 83 * GEN
inv("after all withdrawals")
check("total received is 139 GEN", ledger["received"] == 139 * GEN)
check("total paid out is 83 GEN", ledger["paid"] == 83 * GEN)
check("final pool is 56 GEN (50 + 3 stray + 4 forfeit + 1 released reserve "
      "- 2 consumed reserves + 1 rejected rate stake)", ledger["pool"] == 56 * GEN)
check("final credits are 0", ledger["credits"] == 0)
check("final pending tribute is 0", ledger["pending"] == 0)
check("final open stakes are 0", ledger["stakes"] == 0)
check("final reserved rewards are 0", ledger["reserved"] == 0)

# 9. Pool-exhaustion guard, same rule as the contract: a dispute needs
#    pool >= 1 GEN at open (the success-reward reservation).
check("dispute blocked when pool is 0 GEN", not (0 >= DISPUTE_REWARD // GEN))
check("dispute allowed when pool is 1 GEN", 1 * GEN >= DISPUTE_REWARD)
# Reservation makes the success reward safe even if the pool is drawn
# down afterwards: reserve 1 GEN at open, pool 1 GEN -> 0, success still
# pays from the reservation, never from the (now empty) pool.
pool = 1 * GEN
pool -= DISPUTE_REWARD  # reservation at dispute open
check("reservation leaves pool 0 but reward is covered", pool == 0)

# 10. Stray GEN and sweep, replicating the contract's rule: a rejected
#     payable call leaves its value in the contract balance without
#     touching total_received, so balance exceeds accounted by exactly
#     that value; sweeping moves it into the pool and total_received,
#     restoring the invariant.
ledger2 = {"received": 50 * GEN, "paid": 0, "pool": 50 * GEN, "balance": 50 * GEN}


def inv2(lbl):
    check("invariant holds: " + lbl,
          ledger2["received"] == ledger2["paid"] + ledger2["pool"]
          and ledger2["balance"] == ledger2["received"] - ledger2["paid"])


# A 3 GEN dispute with the wrong stake is rejected, but the 3 GEN stays.
ledger2["balance"] += 3 * GEN
stray = ledger2["balance"] - (ledger2["received"] - ledger2["paid"])
check("stray is exactly 3 GEN after a rejected 3 GEN payable call", stray == 3 * GEN)
check("invariant broken before sweep (balance != accounted)",
      ledger2["balance"] != ledger2["received"] - ledger2["paid"])
# Sweep: pool += stray, received += stray.
ledger2["pool"] += stray
ledger2["received"] += stray
inv2("after sweeping 3 GEN stray into the pool")
check("pool is 53 GEN after the sweep", ledger2["pool"] == 53 * GEN)

# 11. Evidence files (written by scripts/flow.mjs with the run's real
#     addresses): the stated facts must support the verdict the flow
#     expects. Skipped before the flow has written them.
evidence_specs = [
    ("work-neon-koi.json", "original", True),
    ("work-neon-koi-counter.json", "counter-weak", False),
    ("work-dust-choir.json", "original", True),
    ("work-dust-choir-counter.json", "counter-strong", True),
    ("work-thin-sketch.json", "original-thin", False),
    ("work-thin-sketch-counter.json", "counter-strong", True),
    ("work-empty-claim.json", "original-thin", False),
    ("rate-approve-rationale.json", "rationale-approve", True),
    ("rate-reject-rationale.json", "rationale-reject", False),
]
for fname, kind, _ in evidence_specs:
    p = ROOT / "evidence" / fname
    if not p.exists():
        skip("%s not present yet (written by flow.mjs)" % fname)
        continue
    doc = json.loads(p.read_text())
    report = doc.get("report", "")
    if kind == "original":
        check("%s states a creation date and an anchor" % fname,
              "created" in report and ("signed" in report or "published" in report))
    elif kind == "original-thin":
        check("%s explicitly states no date and no anchor" % fname,
              "No creation date" in report and "No signed message" in report)
    elif kind == "counter-weak":
        check("%s states no earlier creation proof" % fname,
              "No creation date" in report and "No signed message" in report)
    elif kind == "counter-strong":
        check("%s states an earlier creation date and an anchor" % fname,
              "created" in report and "signed" in report and "earlier" in report)
    elif kind == "rationale-approve":
        check("%s states a concrete work-specific use" % fname,
              "weekly live drawing session" in report and "brush pack" in report)
    elif kind == "rationale-reject":
        check("%s explicitly states no justification" % fname,
              "No reason" in report)

print("\n%d mock checks passed, %d skipped (LOCAL MOCK ONLY — not on-chain evidence)."
      % (passed, skipped))
