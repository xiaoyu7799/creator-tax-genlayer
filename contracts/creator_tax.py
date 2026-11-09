# v0.1.0
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

# contracts/creator_tax.py
# GenLayer Intelligent Contract: Creator Tax — creator trading-tax sponsorship.
# Target Network: GenLayer Stable Studionet (Chain ID 61999, RPC https://studio.genlayer.com/api)
#
# Real testnet GEN economics (Studionet GEN is free from the faucet, zero
# cash cost; 1 GEN = 10^18 wei). There is no demo ledger and no free
# funds: the sponsorship pool is filled with real GEN by deposit_funding,
# every sponsorship transfer is real GEN, and every stake and reward is
# real GEN.
#
# What this contract does
# -----------------------
# 1. Anyone registers a creative work with evidence of authorship:
#    register_work (title + evidence URL). The work starts REGISTERED at
#    the default tribute rate of 100 basis points (1%).
# 2. Anyone sponsors a work with a real GEN transfer:
#    transfer_with_tribute (payable). The tribute is amount * rate_bp /
#    10000 with integer division; the remainder goes to the recipient as
#    an immediately withdrawable credit, and the tribute is recorded as
#    pending tax for the work's current creator. The creator moves it to
#    a withdrawable credit with claim_credit, then withdraws it with
#    withdraw_credit (pull payment).
# 3. Attribution is decided by consensus, in two rounds with DIFFERENT
#    inputs. Round 1 (resolve_attribution with no open dispute) reads
#    only the original registration evidence: ESTABLISHED means the
#    evidence explicitly states a creation date and a verifiable anchor
#    tying the work to the registered creator; otherwise NOT_ESTABLISHED
#    and the work is marked DISPUTED. A dispute (dispute_attribution)
#    stakes 4 GEN and must supply a counter-evidence URL, which is
#    stored in the dispute. Round 2 (resolve_attribution with an open
#    dispute) fetches BOTH the original evidence and the counter-evidence
#    and decides KEEP or REASSIGN. Because round 2 sees evidence round 1
#    never saw, a flip has a real mechanism behind it: it is not the
#    same evidence re-run. If round 2 keeps the registered creator, the
#    4 GEN stake is forfeited into the sponsorship pool. If it reassigns
#    the work, the first pending verdict is kept as a CONTRADICTION
#    witness, the challenger is credited the 4 GEN stake back plus a
#    1 GEN reward, and later tribute routes to the new creator.
# 4. The tribute rate itself is decided by consensus. The current
#    creator proposes a new tier (propose_rate, 1 GEN stake, tiers only
#    0 / 100 / 200 basis points) with a rationale URL; resolve_rate
#    fetches the work evidence and the rationale and decides APPROVE or
#    REJECT. APPROVE changes the rate and refunds the 1 GEN stake as a
#    credit; REJECT forfeits the stake into the pool and leaves the rate
#    unchanged.
# 5. Equivalence requires EXACT equality of the verdict and of the
#    SHA-256 of every fetched evidence body. A leader output that differs
#    in any of those is rejected. Two validator-compatible outputs
#    therefore cannot store a different rate tier, a different creator,
#    or a different tribute amount: the spread in every stored core
#    value is exactly 0. The tribute split itself is deterministic
#    integer division with no tolerance anywhere. If the judges disagree,
#    nothing is stored and the work stays in its current state.
# 6. All GEN movement is pull-payment: finalization only records a
#    credit (wei integer); the beneficiary withdraws it themselves with
#    withdraw_credit, which zeroes the credit before transferring. The
#    ledger invariant is:
#      total_received == total_paid_out + funding_pool + reserved_rewards
#                         + open_stakes + credits + pending_tribute
#    and the contract balance equals total_received - total_paid_out.
#    One exception is handled explicitly: a payable call the contract
#    rejects (a wrong dispute stake, for example) still leaves its
#    attached GEN in the contract balance, because the state change
#    rolls back but the value transfer does not. That unaccounted GEN is
#    visible as stray_wei in get_ledger and is swept into the funding
#    pool by sweep_stray_gen, which adjusts total_received by the same
#    amount so the invariant holds again.
# 7. Work lifecycle: REGISTERED -> ATTRIBUTION_REVIEW -> CONFIRMED /
#    DISPUTED / REASSIGNED. A work whose round-1 evidence cannot
#    establish its creator is DISPUTED (attribution unproven). Rate
#    proposals go RATE_PENDING -> RATE_ACTIVE (resolved). Creator
#    evolution is tracked from zero: works registered, cumulative
#    tribute earned, attribution wins and losses, rate proposals
#    approved and rejected; the leaderboard ranks creators by cumulative
#    tribute earned.

import json

from genlayer import *

# =============================================================================
# PURE-PYTHON SHA-256 (no dependency on unverified stdlib hashlib in GenVM)
# =============================================================================
_K256 = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
]


def _rotr(x: int, n: int) -> int:
    return ((x >> n) | (x << (32 - n))) & 0xFFFFFFFF


def pure_sha256_hex(msg_str: str) -> str:
    data = bytearray(msg_str.encode("utf-8"))
    bit_len = len(data) * 8
    data.append(0x80)
    while (len(data) % 64) != 56:
        data.append(0x00)
    for i in range(7, -1, -1):
        data.append((bit_len >> (i * 8)) & 0xFF)
    h = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    ]
    for offset in range(0, len(data), 64):
        w = [0] * 64
        for i in range(16):
            j = offset + i * 4
            w[i] = (data[j] << 24) | (data[j + 1] << 16) | (data[j + 2] << 8) | data[j + 3]
        for i in range(16, 64):
            s0 = _rotr(w[i - 15], 7) ^ _rotr(w[i - 15], 18) ^ (w[i - 15] >> 3)
            s1 = _rotr(w[i - 2], 17) ^ _rotr(w[i - 2], 19) ^ (w[i - 2] >> 10)
            w[i] = (w[i - 16] + s0 + w[i - 7] + s1) & 0xFFFFFFFF
        a, b, c, d, e, f, g, hh = h
        for i in range(64):
            S1 = _rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25)
            ch = (e & f) ^ ((~e & 0xFFFFFFFF) & g)
            temp1 = (hh + S1 + ch + _K256[i] + w[i]) & 0xFFFFFFFF
            S0 = _rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22)
            maj = (a & b) ^ (a & c) ^ (b & c)
            temp2 = (S0 + maj) & 0xFFFFFFFF
            hh, g, f, e, d, c, b, a = g, f, e, (d + temp1) & 0xFFFFFFFF, c, b, a, (temp1 + temp2) & 0xFFFFFFFF
        h = [(h[idx] + val) & 0xFFFFFFFF for idx, val in enumerate([a, b, c, d, e, f, g, hh])]
    hex_chars = "0123456789abcdef"
    out = []
    for word in h:
        for shift in (28, 24, 20, 16, 12, 8, 4, 0):
            out.append(hex_chars[(word >> shift) & 0xF])
    return "".join(out)


# =============================================================================
# RATE TIERS, VERDICTS, ECONOMICS (all exact integers, no float)
# =============================================================================
RATE_TIERS = (0, 100, 200)
RATE_DEFAULT_BP = 100
RATE_DENOMINATOR = 10000

# Real GEN economics, in wei (1 GEN = 10^18 wei).
GEN_WEI = 10 ** 18
DISPUTE_STAKE_WEI = 4 * GEN_WEI
DISPUTE_SUCCESS_REWARD_WEI = 1 * GEN_WEI
RATE_STAKE_WEI = 1 * GEN_WEI


def tribute_for(amount_wei: int, rate_bp: int) -> int:
    # Integer division; any remainder stays with the recipient.
    return (int(amount_wei) * int(rate_bp)) // RATE_DENOMINATOR


def _is_hex_address(addr: str) -> bool:
    if len(addr) != 42:
        return False
    if addr[0] != "0" or addr[1] != "x":
        return False
    for ch in addr[2:]:
        ok = (ch >= "0" and ch <= "9") or (ch >= "a" and ch <= "f") or (ch >= "A" and ch <= "F")
        if not ok:
            return False
    return True


def _check_evidence_url(url: str):
    if not url.startswith("https://"):
        raise Exception("EVIDENCE_URL_MUST_BE_HTTPS")
    if len(url) > 300:
        raise Exception("EVIDENCE_URL_TOO_LONG")


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


class CreatorTax(gl.Contract):
    state_json: str

    def __init__(self):
        state = {
            "next_work_id": 0,
            "funding_pool_wei": 0,
            "total_received_wei": 0,
            "total_paid_out_wei": 0,
            "dispute_stake_wei": DISPUTE_STAKE_WEI,
            "dispute_success_reward_wei": DISPUTE_SUCCESS_REWARD_WEI,
            "rate_stake_wei": RATE_STAKE_WEI,
            "rate_default_bp": RATE_DEFAULT_BP,
            "works": {},
            "work_order": [],
            "credits": {},
            "creator_stats": {},
        }
        self.state_json = json.dumps(state)

    # -- deterministic helpers --------------------------------------------

    def _load(self):
        return json.loads(self.state_json)

    def _save(self, state):
        self.state_json = json.dumps(state)

    def _sender(self) -> str:
        return gl.message.sender_address.as_hex.lower()

    def _ensure_creator_stats(self, state, addr: str):
        if addr not in state["creator_stats"]:
            state["creator_stats"][addr] = {
                "works_registered": 0,
                "tax_earned_wei": 0,
                "attribution_wins": 0,
                "attribution_losses": 0,
                "rate_proposals_approved": 0,
                "rate_proposals_rejected": 0,
            }

    def _load_work(self, state, work_id: u256):
        key = str(int(work_id))
        if key not in state["works"]:
            raise Exception("WORK_NOT_FOUND")
        return state["works"][key]

    def _pending_tribute_total(self, state) -> int:
        total = 0
        for work in state["works"].values():
            for amount in work["tax_pending"].values():
                total += int(amount)
        return total

    # -- writes -------------------------------------------------------------

    @gl.public.write.payable
    def deposit_funding(self) -> str:
        value = int(gl.message.value)
        if value == 0:
            raise Exception("FUNDING_MUST_SEND_GEN")
        sender = self._sender()
        state = self._load()
        state["total_received_wei"] = int(state["total_received_wei"]) + value
        state["funding_pool_wei"] = int(state["funding_pool_wei"]) + value
        self._save(state)
        return json.dumps({
            "funder": sender,
            "deposited_wei": value,
            "deposited_gen": value // GEN_WEI,
            "funding_pool_wei": int(state["funding_pool_wei"]),
        })

    @gl.public.write
    def register_work(self, title: str, evidence_url: str, evidence_note: str) -> u256:
        if len(title) == 0 or len(title) > 200:
            raise Exception("TITLE_MUST_BE_1_TO_200_CHARS")
        _check_evidence_url(evidence_url)
        if len(evidence_note) > 500:
            raise Exception("EVIDENCE_NOTE_TOO_LONG")
        sender = self._sender()
        state = self._load()
        self._ensure_creator_stats(state, sender)
        work_id = int(state["next_work_id"])
        state["next_work_id"] = work_id + 1
        work = {
            "work_id": work_id,
            "title": title,
            "creator": sender,
            "evidence_url": evidence_url,
            "evidence_note": evidence_note,
            "rate_bp": RATE_DEFAULT_BP,
            "status": "REGISTERED",
            "pending_attribution": None,
            "pending_round": 0,
            "evaluations": 0,
            "first_evidence_sha256": None,
            "final_attribution": None,
            "counter_evidence_sha256": None,
            "dispute": None,
            "rate_proposal": None,
            "witnesses": [],
            "tax_pending": {},
            "tax_earned_wei": 0,
            "volume_wei": 0,
            "transfers": 0,
        }
        state["works"][str(work_id)] = work
        state["work_order"].append(work_id)
        state["creator_stats"][sender]["works_registered"] = int(state["creator_stats"][sender]["works_registered"]) + 1
        self._save(state)
        return u256(work_id)

    @gl.public.write.payable
    def transfer_with_tribute(self, work_id: u256, recipient: str) -> str:
        # Pure validation first (recipient, work exists), value check
        # after: a probe with 0 GEN can exercise the business checks
        # without leaving stray GEN behind.
        if not _is_hex_address(recipient):
            raise Exception("INVALID_RECIPIENT_ADDRESS")
        state = self._load()
        work = self._load_work(state, work_id)
        value = int(gl.message.value)
        if value == 0:
            raise Exception("TRANSFER_MUST_SEND_GEN")
        sender = self._sender()
        rate_bp = int(work["rate_bp"])
        tribute = tribute_for(value, rate_bp)
        recipient_share = value - tribute
        creator = work["creator"]
        recipient_key = recipient.lower()
        state["total_received_wei"] = int(state["total_received_wei"]) + value
        prev_credit = int(state["credits"].get(recipient_key, 0))
        state["credits"][recipient_key] = prev_credit + recipient_share
        pending = work["tax_pending"]
        prev_pending = int(pending.get(creator, 0))
        pending[creator] = prev_pending + tribute
        work["tax_earned_wei"] = int(work["tax_earned_wei"]) + tribute
        work["volume_wei"] = int(work["volume_wei"]) + value
        work["transfers"] = int(work["transfers"]) + 1
        self._ensure_creator_stats(state, creator)
        stats = state["creator_stats"][creator]
        stats["tax_earned_wei"] = int(stats["tax_earned_wei"]) + tribute
        self._save(state)
        return json.dumps({
            "work_id": int(work_id),
            "sender": sender,
            "recipient": recipient_key,
            "amount_wei": value,
            "rate_bp": rate_bp,
            "tribute_wei": tribute,
            "recipient_share_wei": recipient_share,
            "creator": creator,
        })

    @gl.public.write.payable
    def dispute_attribution(self, work_id: u256, claimed_creator: str, counter_evidence_url: str, counter_note: str) -> str:
        # Pure validation first (addresses, URLs, work state, claimed
        # creator), value check last: a probe with 0 GEN can exercise
        # the business checks without leaving stray GEN behind, while
        # a wrong-stake probe on an otherwise valid dispute exercises
        # the value check and leaves the stray the sweep step handles.
        if not _is_hex_address(claimed_creator):
            raise Exception("INVALID_CLAIMED_CREATOR_ADDRESS")
        _check_evidence_url(counter_evidence_url)
        if len(counter_note) > 500:
            raise Exception("COUNTER_NOTE_TOO_LONG")
        sender = self._sender()
        state = self._load()
        work = self._load_work(state, work_id)
        if work["status"] not in ("ATTRIBUTION_REVIEW", "DISPUTED"):
            raise Exception("DISPUTE_REQUIRES_FIRST_ATTRIBUTION")
        if work["dispute"] is not None:
            raise Exception("DISPUTE_ALREADY_OPEN")
        if claimed_creator.lower() == work["creator"]:
            raise Exception("CLAIMED_MUST_DIFFER_FROM_CREATOR")
        if sender == work["creator"]:
            raise Exception("CREATOR_MAY_NOT_DISPUTE_OWN_WORK")
        if int(state["funding_pool_wei"]) < DISPUTE_SUCCESS_REWARD_WEI:
            raise Exception("FUNDING_POOL_TOO_LOW_FOR_DISPUTE_REWARD")
        value = int(gl.message.value)
        if value != DISPUTE_STAKE_WEI:
            raise Exception("DISPUTE_STAKE_MUST_BE_4_GEN")
        self._ensure_creator_stats(state, sender)
        # Reserve the 1 GEN success reward from the pool now, so a later
        # successful dispute can always be paid even if the pool is
        # drawn down in between. The stake itself is held in the dispute.
        state["funding_pool_wei"] = int(state["funding_pool_wei"]) - DISPUTE_SUCCESS_REWARD_WEI
        state["total_received_wei"] = int(state["total_received_wei"]) + value
        work["dispute"] = {
            "challenger": sender,
            "claimed_creator": claimed_creator.lower(),
            "counter_evidence_url": counter_evidence_url,
            "counter_note": counter_note,
            "stake_wei": value,
            "reserved_wei": DISPUTE_SUCCESS_REWARD_WEI,
        }
        work["status"] = "ATTRIBUTION_REVIEW"
        self._save(state)
        return json.dumps(self._load_work(self._load(), work_id))

    @gl.public.write
    def resolve_attribution(self, work_id: u256) -> str:
        sender = self._sender()
        state = self._load()
        work = self._load_work(state, work_id)
        if sender == work["creator"]:
            raise Exception("CREATOR_MAY_NOT_JUDGE_OWN_WORK")
        if work["status"] in ("CONFIRMED", "REASSIGNED"):
            raise Exception("WORK_ALREADY_DECIDED")
        disputed = work["dispute"] is not None
        if not disputed and work["status"] != "REGISTERED":
            raise Exception("ATTRIBUTION_NOT_OPEN")
        if disputed and work["status"] != "ATTRIBUTION_REVIEW":
            raise Exception("ATTRIBUTION_NOT_OPEN")
        evidence_url = work["evidence_url"]
        registered_creator = work["creator"]
        title = work["title"]
        if disputed:
            counter_url = work["dispute"]["counter_evidence_url"]
            claimed_creator = work["dispute"]["claimed_creator"]
        else:
            counter_url = None
            claimed_creator = None

        def judge():
            def fetch(url):
                try:
                    response = gl.nondet.web.request(url, method="GET")
                except Exception:
                    raise Exception("EVIDENCE_FETCH_FAILED_PENDING_RETRY")
                if response.status != 200:
                    raise Exception("EVIDENCE_FETCH_FAILED_PENDING_RETRY")
                body = response.body
                if isinstance(body, bytes):
                    text = body.decode("utf-8")
                else:
                    text = str(body)
                if len(text) == 0:
                    raise Exception("EVIDENCE_EMPTY_PENDING_RETRY")
                return text

            if not disputed:
                text = fetch(evidence_url)
                prompt = (
                    "You are a strict attribution analyst. Read the authorship evidence below for the work "
                    "\"" + title + "\", registered to creator " + registered_creator + ". "
                    "Return ESTABLISHED only if the evidence explicitly states a creation date AND a "
                    "verifiable anchor (a signed message, a publication link, or a named first-publication "
                    "venue) tying the work to the registered creator. If the evidence gives no creation "
                    "date, or no anchor of any kind, return NOT_ESTABLISHED. Do not infer authorship "
                    "from a bare claim of ownership.\n"
                    "Respond with ONLY a JSON object, no prose: {\"verdict\": \"ESTABLISHED\"} or "
                    "{\"verdict\": \"NOT_ESTABLISHED\"}.\n"
                    "Evidence:\n" + text[:6000]
                )
                parsed = gl.nondet.exec_prompt(prompt, response_format="json")
                if isinstance(parsed, str):
                    parsed = json.loads(parsed)
                if not isinstance(parsed, dict) or parsed.get("verdict") not in ("ESTABLISHED", "NOT_ESTABLISHED"):
                    raise Exception("INVALID_JUDGE_OUTPUT_PENDING_RETRY")
                return {
                    "verdict": parsed["verdict"],
                    "evidence_sha256": pure_sha256_hex(text),
                }
            original_text = fetch(evidence_url)
            counter_text = fetch(counter_url)
            prompt = (
                "You are a strict attribution analyst. Two evidence sets describe who created the work "
                "\"" + title + "\". The registered creator is " + registered_creator + "; the challenger "
                "claims the creator is " + claimed_creator + ". Compare both evidence sets. The creator "
                "who is shown to have created the work FIRST, with an explicit creation date and a "
                "verifiable anchor (a signed message, a publication link, or a named first-publication "
                "venue), is the lawful creator. Return REASSIGN only if the counter-evidence explicitly "
                "proves the claimed creator created the work earlier than the registered creator, with "
                "both an earlier explicit creation date AND a verifiable anchor. Otherwise return KEEP. "
                "A later post, a bare ownership claim, or a resemblance with no creation date and no "
                "anchor never justifies REASSIGN.\n"
                "Respond with ONLY a JSON object, no prose: {\"verdict\": \"KEEP\"} or "
                "{\"verdict\": \"REASSIGN\"}.\n"
                "Original registration evidence:\n" + original_text[:6000] + "\n"
                "Counter-evidence:\n" + counter_text[:6000]
            )
            parsed = gl.nondet.exec_prompt(prompt, response_format="json")
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            if not isinstance(parsed, dict) or parsed.get("verdict") not in ("KEEP", "REASSIGN"):
                raise Exception("INVALID_JUDGE_OUTPUT_PENDING_RETRY")
            return {
                "verdict": parsed["verdict"],
                "original_sha256": pure_sha256_hex(original_text),
                "counter_sha256": pure_sha256_hex(counter_text),
            }

        def validate(leader_result):
            if isinstance(leader_result, gl.vm.UserError):
                try:
                    judge()
                except Exception:
                    return True
                return False
            if not isinstance(leader_result, gl.vm.Return):
                return False
            leader = leader_result.calldata
            if not isinstance(leader, dict):
                return False
            try:
                own = judge()
            except Exception:
                return False
            if leader.get("verdict") != own["verdict"]:
                return False
            if not disputed:
                if leader.get("evidence_sha256") != own["evidence_sha256"]:
                    return False
            else:
                if leader.get("original_sha256") != own["original_sha256"]:
                    return False
                if leader.get("counter_sha256") != own["counter_sha256"]:
                    return False
            return True

        result = gl.vm.run_nondet_unsafe(judge, validate)
        verdict = result["verdict"]

        state = self._load()
        work = self._load_work(state, work_id)
        if work["status"] in ("CONFIRMED", "REASSIGNED"):
            raise Exception("WORK_ALREADY_DECIDED")
        work["evaluations"] = int(work["evaluations"]) + 1
        work["pending_round"] = int(work["pending_round"]) + 1
        if not disputed:
            if verdict not in ("ESTABLISHED", "NOT_ESTABLISHED"):
                raise Exception("VERDICT_MISMATCH_WITH_ROUND")
            work["first_evidence_sha256"] = result["evidence_sha256"]
            if verdict == "ESTABLISHED":
                work["pending_attribution"] = "KEEP"
                work["status"] = "ATTRIBUTION_REVIEW"
            else:
                work["pending_attribution"] = "NOT_ESTABLISHED"
                work["status"] = "DISPUTED"
        else:
            if verdict not in ("KEEP", "REASSIGN"):
                raise Exception("VERDICT_MISMATCH_WITH_ROUND")
            dispute = work["dispute"]
            first_verdict = work["pending_attribution"]
            challenger = dispute["challenger"]
            claimed = dispute["claimed_creator"]
            stake_wei = int(dispute["stake_wei"])
            reserved_wei = int(dispute["reserved_wei"])
            work["counter_evidence_sha256"] = result["counter_sha256"]
            self._ensure_creator_stats(state, challenger)
            self._ensure_creator_stats(state, work["creator"])
            if verdict == "KEEP":
                # Dispute failed: the 4 GEN stake and the 1 GEN reservation
                # both go into the funding pool; no credit for the challenger.
                state["funding_pool_wei"] = int(state["funding_pool_wei"]) + stake_wei + reserved_wei
                challenger_stats = state["creator_stats"][challenger]
                challenger_stats["attribution_losses"] = int(challenger_stats["attribution_losses"]) + 1
                creator_stats = state["creator_stats"][work["creator"]]
                creator_stats["attribution_wins"] = int(creator_stats["attribution_wins"]) + 1
                work["witnesses"].append({
                    "witness_id": "wit-" + str(work_id) + "-r" + str(work["pending_round"]),
                    "round": int(work["pending_round"]),
                    "kind": "FAILED_DISPUTE",
                    "challenger": challenger,
                    "claimed_creator": claimed,
                    "first_attribution": first_verdict,
                    "second_verdict": verdict,
                    "stake_forfeited_wei": stake_wei,
                    "note": "Second evaluation agreed with the first attribution; dispute failed; 4 GEN stake forfeited to the funding pool.",
                })
                work["final_attribution"] = "KEEP"
                work["status"] = "CONFIRMED"
            else:
                # Dispute succeeded: the challenger is credited the 4 GEN
                # stake back plus a 1 GEN reward (the reservation made at
                # dispute time covers the reward, so the pool is never
                # overdrawn). The first pending attribution survives as a
                # witness, and later tribute routes to the new creator.
                credit = stake_wei + reserved_wei
                prev = int(state["credits"].get(challenger, 0))
                state["credits"][challenger] = prev + credit
                old_creator = work["creator"]
                challenger_stats = state["creator_stats"][challenger]
                challenger_stats["attribution_wins"] = int(challenger_stats["attribution_wins"]) + 1
                creator_stats = state["creator_stats"][old_creator]
                creator_stats["attribution_losses"] = int(creator_stats["attribution_losses"]) + 1
                work["witnesses"].append({
                    "witness_id": "wit-" + str(work_id) + "-r" + str(work["pending_round"]),
                    "round": int(work["pending_round"]),
                    "kind": "CONTRADICTION",
                    "challenger": challenger,
                    "claimed_creator": claimed,
                    "first_attribution": first_verdict,
                    "first_evidence_sha256": work["first_evidence_sha256"],
                    "second_verdict": verdict,
                    "challenger_credit_wei": credit,
                    "note": "Second evaluation, reading the counter-evidence the first round never saw, disagreed with the first attribution; first attribution kept as witness only; challenger credited 4 GEN stake refund + 1 GEN reward; work reassigned.",
                })
                work["creator"] = claimed
                work["final_attribution"] = "REASSIGN"
                work["status"] = "REASSIGNED"
            work["dispute"] = None
        self._save(state)
        return json.dumps(self._load_work(self._load(), work_id))

    @gl.public.write.payable
    def propose_rate(self, work_id: u256, new_rate_bp: u256, rationale_url: str, rationale_note: str) -> str:
        # Pure validation first (URLs, proposer, open proposal, work
        # state, tier), value check last: a probe with 0 GEN can
        # exercise the business checks without leaving stray GEN behind.
        _check_evidence_url(rationale_url)
        if len(rationale_note) > 500:
            raise Exception("RATIONALE_NOTE_TOO_LONG")
        sender = self._sender()
        state = self._load()
        work = self._load_work(state, work_id)
        if sender != work["creator"]:
            raise Exception("ONLY_CREATOR_MAY_PROPOSE_RATE")
        if work["rate_proposal"] is not None and work["rate_proposal"]["status"] == "RATE_PENDING":
            raise Exception("RATE_PROPOSAL_ALREADY_OPEN")
        if work["status"] in ("ATTRIBUTION_REVIEW", "DISPUTED"):
            raise Exception("RATE_PROPOSAL_BLOCKED_WHILE_ATTRIBUTION_OPEN")
        new_rate = int(new_rate_bp)
        if new_rate not in RATE_TIERS:
            raise Exception("RATE_TIER_MUST_BE_0_100_OR_200_BP")
        if new_rate == int(work["rate_bp"]):
            raise Exception("RATE_MUST_CHANGE")
        value = int(gl.message.value)
        if value != RATE_STAKE_WEI:
            raise Exception("RATE_STAKE_MUST_BE_1_GEN")
        state["total_received_wei"] = int(state["total_received_wei"]) + value
        work["rate_proposal"] = {
            "proposer": sender,
            "proposed_rate_bp": new_rate,
            "current_rate_bp": int(work["rate_bp"]),
            "rationale_url": rationale_url,
            "rationale_note": rationale_note,
            "stake_wei": value,
            "status": "RATE_PENDING",
            "outcome": None,
            "work_sha256": None,
            "rationale_sha256": None,
        }
        self._save(state)
        return json.dumps(self._load_work(self._load(), work_id))

    @gl.public.write
    def resolve_rate(self, work_id: u256) -> str:
        sender = self._sender()
        state = self._load()
        work = self._load_work(state, work_id)
        proposal = work["rate_proposal"]
        if proposal is None or proposal["status"] != "RATE_PENDING":
            raise Exception("NO_OPEN_RATE_PROPOSAL")
        if sender == proposal["proposer"]:
            raise Exception("PROPOSER_MAY_NOT_JUDGE_OWN_PROPOSAL")
        evidence_url = work["evidence_url"]
        rationale_url = proposal["rationale_url"]
        title = work["title"]
        proposed_rate = int(proposal["proposed_rate_bp"])
        current_rate = int(proposal["current_rate_bp"])

        def judge():
            def fetch(url):
                try:
                    response = gl.nondet.web.request(url, method="GET")
                except Exception:
                    raise Exception("EVIDENCE_FETCH_FAILED_PENDING_RETRY")
                if response.status != 200:
                    raise Exception("EVIDENCE_FETCH_FAILED_PENDING_RETRY")
                body = response.body
                if isinstance(body, bytes):
                    text = body.decode("utf-8")
                else:
                    text = str(body)
                if len(text) == 0:
                    raise Exception("EVIDENCE_EMPTY_PENDING_RETRY")
                return text

            work_text = fetch(evidence_url)
            rationale_text = fetch(rationale_url)
            prompt = (
                "You are a strict rate-review analyst. A creator proposes changing the tribute rate on the "
                "work \"" + title + "\" from " + str(current_rate) + " basis points to " + str(proposed_rate) + " "
                "basis points. Read the work evidence and the proposal rationale. Return APPROVE only if "
                "the rationale states a concrete, work-specific use for the revenue change AND the work "
                "evidence shows the work exists with a named creator. If the rationale states no "
                "justification, or no concrete use, return REJECT. Do not approve a rate change on a "
                "vague wish alone.\n"
                "Respond with ONLY a JSON object, no prose: {\"verdict\": \"APPROVE\"} or "
                "{\"verdict\": \"REJECT\"}.\n"
                "Work evidence:\n" + work_text[:6000] + "\n"
                "Proposal rationale:\n" + rationale_text[:6000]
            )
            parsed = gl.nondet.exec_prompt(prompt, response_format="json")
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            if not isinstance(parsed, dict) or parsed.get("verdict") not in ("APPROVE", "REJECT"):
                raise Exception("INVALID_JUDGE_OUTPUT_PENDING_RETRY")
            return {
                "verdict": parsed["verdict"],
                "work_sha256": pure_sha256_hex(work_text),
                "rationale_sha256": pure_sha256_hex(rationale_text),
            }

        def validate(leader_result):
            if isinstance(leader_result, gl.vm.UserError):
                try:
                    judge()
                except Exception:
                    return True
                return False
            if not isinstance(leader_result, gl.vm.Return):
                return False
            leader = leader_result.calldata
            if not isinstance(leader, dict):
                return False
            try:
                own = judge()
            except Exception:
                return False
            if leader.get("verdict") != own["verdict"]:
                return False
            if leader.get("work_sha256") != own["work_sha256"]:
                return False
            if leader.get("rationale_sha256") != own["rationale_sha256"]:
                return False
            return True

        result = gl.vm.run_nondet_unsafe(judge, validate)
        verdict = result["verdict"]

        state = self._load()
        work = self._load_work(state, work_id)
        proposal = work["rate_proposal"]
        if proposal is None or proposal["status"] != "RATE_PENDING":
            raise Exception("NO_OPEN_RATE_PROPOSAL")
        stake_wei = int(proposal["stake_wei"])
        proposer = proposal["proposer"]
        proposal["work_sha256"] = result["work_sha256"]
        proposal["rationale_sha256"] = result["rationale_sha256"]
        proposal["status"] = "RATE_ACTIVE"
        proposal["outcome"] = verdict
        self._ensure_creator_stats(state, proposer)
        stats = state["creator_stats"][proposer]
        if verdict == "APPROVE":
            work["rate_bp"] = int(proposal["proposed_rate_bp"])
            prev = int(state["credits"].get(proposer, 0))
            state["credits"][proposer] = prev + stake_wei
            stats["rate_proposals_approved"] = int(stats["rate_proposals_approved"]) + 1
        else:
            state["funding_pool_wei"] = int(state["funding_pool_wei"]) + stake_wei
            stats["rate_proposals_rejected"] = int(stats["rate_proposals_rejected"]) + 1
        self._save(state)
        return json.dumps(self._load_work(self._load(), work_id))

    @gl.public.write
    def claim_credit(self, work_id: u256) -> str:
        sender = self._sender()
        state = self._load()
        work = self._load_work(state, work_id)
        if sender != work["creator"]:
            raise Exception("ONLY_CREATOR_MAY_CLAIM_TAX")
        pending = int(work["tax_pending"].get(sender, 0))
        if pending == 0:
            raise Exception("NO_PENDING_TAX")
        work["tax_pending"][sender] = 0
        prev = int(state["credits"].get(sender, 0))
        state["credits"][sender] = prev + pending
        self._save(state)
        return json.dumps({
            "creator": sender,
            "work_id": int(work_id),
            "claimed_wei": pending,
            "claimed_gen": pending // GEN_WEI,
            "credit_wei": int(state["credits"][sender]),
        })

    @gl.public.write
    def withdraw_credit(self) -> str:
        sender = self._sender()
        state = self._load()
        amount = int(state["credits"].get(sender, 0))
        if amount == 0:
            raise Exception("NO_CREDIT")
        # Pull payment: zero the credit BEFORE transferring, so a failed
        # or re-entered transfer can never pay twice.
        state["credits"][sender] = 0
        state["total_paid_out_wei"] = int(state["total_paid_out_wei"]) + amount
        self._save(state)
        _Recipient(Address(sender)).emit_transfer(value=u256(amount))
        return json.dumps({
            "beneficiary": sender,
            "withdrawn_wei": amount,
            "withdrawn_gen": amount // GEN_WEI,
            "total_paid_out_wei": int(state["total_paid_out_wei"]),
        })

    @gl.public.write
    def sweep_stray_gen(self) -> str:
        # A payable call that the contract rejects (wrong dispute stake,
        # for example) still leaves its attached GEN in the contract
        # balance: the state change rolls back, but the value transfer
        # does not. That GEN is unaccounted until it is swept. Anyone may
        # sweep it: the unaccounted balance is moved into the funding pool
        # and total_received is adjusted by the same amount, so the ledger
        # invariant holds again. No accounted GEN can ever be swept: the
        # swept amount is exactly balance minus accounted, and it is zero
        # when every inflow was accounted.
        state = self._load()
        accounted = int(state["total_received_wei"]) - int(state["total_paid_out_wei"])
        stray = int(self.balance) - accounted
        if stray < 0:
            raise Exception("NEGATIVE_STRAY_UNEXPECTED")
        if stray == 0:
            raise Exception("NO_STRAY_GEN")
        state["total_received_wei"] = int(state["total_received_wei"]) + stray
        state["funding_pool_wei"] = int(state["funding_pool_wei"]) + stray
        self._save(state)
        return json.dumps({
            "swept_wei": stray,
            "swept_gen": stray // GEN_WEI,
            "funding_pool_wei": int(state["funding_pool_wei"]),
            "total_received_wei": int(state["total_received_wei"]),
        })

    # -- views --------------------------------------------------------------

    @gl.public.view
    def get_work(self, work_id: u256) -> str:
        state = self._load()
        return json.dumps(self._load_work(state, work_id))

    @gl.public.view
    def get_work_count(self) -> u256:
        state = self._load()
        return u256(len(state["work_order"]))

    @gl.public.view
    def list_works(self, offset: u256, limit: u256) -> str:
        if limit < 1 or limit > 20:
            raise Exception("LIMIT_MUST_BE_1_TO_20")
        state = self._load()
        order = state["work_order"]
        total = len(order)
        start = int(offset)
        if start >= total:
            return json.dumps([])
        end = start + int(limit)
        if end > total:
            end = total
        out = []
        index = start
        while index < end:
            out.append(state["works"][str(order[index])])
            index += 1
        return json.dumps(out)

    @gl.public.view
    def get_credit(self, address: str) -> str:
        state = self._load()
        key = address.lower()
        return json.dumps({"address": key, "credit_wei": int(state["credits"].get(key, 0))})

    @gl.public.view
    def get_creator_stats(self, address: str) -> str:
        state = self._load()
        key = address.lower()
        self._ensure_creator_stats(state, key)
        stats = state["creator_stats"][key]
        return json.dumps({
            "creator": key,
            "works_registered": int(stats["works_registered"]),
            "tax_earned_wei": int(stats["tax_earned_wei"]),
            "attribution_wins": int(stats["attribution_wins"]),
            "attribution_losses": int(stats["attribution_losses"]),
            "rate_proposals_approved": int(stats["rate_proposals_approved"]),
            "rate_proposals_rejected": int(stats["rate_proposals_rejected"]),
        })

    @gl.public.view
    def get_funding_pool(self) -> str:
        state = self._load()
        return json.dumps({
            "funding_pool_wei": int(state["funding_pool_wei"]),
            "dispute_stake_wei": DISPUTE_STAKE_WEI,
            "dispute_success_reward_wei": DISPUTE_SUCCESS_REWARD_WEI,
            "rate_stake_wei": RATE_STAKE_WEI,
            "rate_default_bp": RATE_DEFAULT_BP,
            "rate_tiers_bp": list(RATE_TIERS),
        })

    @gl.public.view
    def get_ledger(self) -> str:
        state = self._load()
        credits_total = 0
        for amount in state["credits"].values():
            credits_total += int(amount)
        pending_total = self._pending_tribute_total(state)
        stakes_total = 0
        reserved_total = 0
        for work in state["works"].values():
            dispute = work.get("dispute")
            if dispute is not None:
                stakes_total += int(dispute["stake_wei"])
                reserved_total += int(dispute["reserved_wei"])
            proposal = work.get("rate_proposal")
            if proposal is not None and proposal["status"] == "RATE_PENDING":
                stakes_total += int(proposal["stake_wei"])
        total_received = int(state["total_received_wei"])
        total_paid_out = int(state["total_paid_out_wei"])
        funding_pool = int(state["funding_pool_wei"])
        contract_balance = int(self.balance)
        accounted = total_received - total_paid_out
        stray = contract_balance - accounted
        invariant = (
            total_received == total_paid_out + funding_pool + reserved_total + stakes_total + credits_total + pending_total
            and contract_balance == accounted
        )
        return json.dumps({
            "total_received_wei": total_received,
            "total_paid_out_wei": total_paid_out,
            "funding_pool_wei": funding_pool,
            "reserved_rewards_wei": reserved_total,
            "open_stakes_wei": stakes_total,
            "credits_wei": credits_total,
            "pending_tribute_wei": pending_total,
            "contract_balance_wei": contract_balance,
            "accounted_wei": accounted,
            "stray_wei": stray,
            "invariant_ok": invariant,
        })

    @gl.public.view
    def get_leaderboard(self, limit: u256) -> str:
        if limit < 1 or limit > 20:
            raise Exception("LIMIT_MUST_BE_1_TO_20")
        state = self._load()
        rows = []
        for creator, stats in state["creator_stats"].items():
            rows.append({
                "creator": creator,
                "works_registered": int(stats["works_registered"]),
                "tax_earned_wei": int(stats["tax_earned_wei"]),
                "attribution_wins": int(stats["attribution_wins"]),
                "attribution_losses": int(stats["attribution_losses"]),
                "rate_proposals_approved": int(stats["rate_proposals_approved"]),
                "rate_proposals_rejected": int(stats["rate_proposals_rejected"]),
            })
        rows.sort(key=lambda r: (-r["tax_earned_wei"], -r["attribution_wins"], r["creator"]))
        return json.dumps(rows[:int(limit)])
