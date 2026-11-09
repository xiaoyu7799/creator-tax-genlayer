# Known limitations

- **One attribution dispute per work.** A work that reaches CONFIRMED or
  REASSIGNED cannot be disputed again. A second, later claim about the
  same work needs a new registration.
- **No deadlines.** The network has no clock source, so an open dispute or
  rate proposal stays open until someone resolves it; there is no automatic
  expiry or timeout.
- **Evidence must stay reachable.** The judges fetch the work evidence,
  counter-evidence and rationale URLs at evaluation time. If a URL is
  down or its content changed, the evaluation fails and stays pending
  until the URL answers again; a changed file is visible as a different
  SHA-256, not silently equated with the earlier bytes.
- **Judgement is bounded by the evidence text.** The verdicts follow what
  the evidence explicitly states (creation dates, verifiable anchors,
  concrete rate rationale). Thin or ambiguous evidence yields
  NOT_ESTABLISHED / KEEP / REJECT rather than a guess.
- **Rate tiers are coarse by design.** Only 0 / 100 / 200 basis points
  exist; there is no continuous rate.
- **Credits wait for withdrawal.** Tribute and rewards sit as credits
  until the beneficiary calls `withdraw_credit`; nothing is pushed
  automatically.
- **Sponsorship transfers are one-way.** A transfer cannot be recalled;
  only the attribution and rate mechanisms can change where future
  tribute goes.
- **Verification used script accounts.** The on-chain flow was run with
  ephemeral test accounts and `sim_fundAccount` testnet GEN; no browser
  wallet path was part of this contract-only delivery.
