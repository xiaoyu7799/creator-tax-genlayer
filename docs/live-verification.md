# Live verification

Network: Stable Studionet (chain 61999). Contract: `0xCc792333d8931791Cad14EB3dc473e666B40b28F`
Explorer: https://explorer-studio.genlayer.com/address/0xCc792333d8931791Cad14EB3dc473e666B40b28F
Checked at: 2026-11-09T15:26:43.105Z

Three earlier deployments of this same source were abandoned: `0xFB0d95D140Eb5f44364a900F1d315546A466aDf7` (deploy tx `0xffbcd4ff73c8d0c66ce6879b2f482f5d537478053f7ec043147ce985edd32ac5`), stopped by a transient RPC gateway failure before any adjudication ran; `0x2292F00D352A7166689F16C28462ab327EA50C90` (deploy tx `0x371c10f5e51989ddfc5d17b1da47b8264b76f3c66ea414a5a5f014ff698d4a15`), stopped by a flow-script assertion bug (a Number-vs-String comparison) after funding and the first transfers; and `0xe8b64e0F5d15c6BA8deA3DFAd5cC43743Bd0cB09` (deploy tx `0x11fb7997705c7e955031eb2629471b75b3b85568855dd76a40a2901479610573`), stopped by a virtual-machine restart after funding, registration and the first transfers. All three runs' ephemeral accounts were lost with their processes. Their faucet testnet GEN (50 GEN + 92 GEN + 92 GEN) stays locked there. This deployment replaces them; the source is unchanged.

## Transactions (all FINALIZED)

- deposit_funding 50 GEN (D): `0x42fa14f2a9c2306f8ecc61f7776db2440484371010a6fcaf6783f2e049de3da9` — FINALIZED
- register_work 0 (Neon Koi): `0x228d1fc48738e52bdf9a2f718f97a727209a3defdda73ce50bd6b1330763f24c` — FINALIZED
- register_work 1 (Dust Choir): `0xb12e54c36842f548791cdcf21eda0ac10f3b8bd390c174544717c215c4e273bd` — FINALIZED
- register_work 2 (Thin Sketch): `0x31c3f4050d1906b403cbd980d9b711de06d168ad0127cbd9b98bf02db0e501e9` — FINALIZED
- transfer_with_tribute work 0: 10 GEN (D -> R): `0x93066453a0d604de00affc24f743641304b8412b9e67ea90d32df543a096b92e` — FINALIZED
- transfer_with_tribute work 0: 7 GEN (E -> R): `0xcde400c7fb35fa43ba847cd506c31e599308f011f96528797579a2b2b814ac40` — FINALIZED
- transfer_with_tribute work 1: 25 GEN (D -> R): `0x741307cce55f5a23fe89cc1627165adb5ac9659bbc1ca4eac4a2381983c95e62` — FINALIZED
- claim_credit work 0 (0.17 GEN): `0xdb85a39222180671833b6b0e6b77c0d3ff12d77c6dbb34ce4390b7d152db2f9e` — FINALIZED
- claim_credit work 1 (0.25 GEN): `0x4663d7c043b22fd5ac507f876641393a54f640142888ee772f445600831f26aa` — FINALIZED
- resolve_attribution 0 (round 1) (attempt 1): `0x44cb28df16b451582acd6f8bc1771eec915eb7280bd5542143a964a1bffdaf9b` — FINALIZED
- dispute_attribution work 0 with 3 GEN stake (rejected probe): `0xaee1de998569f0e46cea16057f29d07bf05663d58d390d1e2db9525421a4de2b` — FINALIZED
- sweep_stray_gen (stray from wrong-stake probe): `0x0ddc8578997cf10bcab58231711ef2049fc7447e418588af1038b460f75d49de` — FINALIZED
- dispute_attribution 0 (4 GEN, weak counter): `0x35b7a7a7409e9b0b657a780264a69144fcd0f114a442b8e000502b1e5b527c2c` — FINALIZED
- resolve_attribution 0 (round 2) (attempt 1): `0x804d49f955baff71beb2dce4e932c37725263f5aead92c53c593743298fe8717` — FINALIZED
- resolve_attribution 1 (round 1) (attempt 1): `0x6093ddcbd38e089e9c91a27fc88a39f65fcd57c0e6a0caf3c365559fecd7de46` — FINALIZED
- dispute_attribution 1 (4 GEN, strong counter): `0x1b416b4c9dd5baf262f56e62f32076d21acbe09bd99d54a614d14cb292515f3a` — FINALIZED
- resolve_attribution 1 (round 2) (attempt 1): `0xa08620ba4a1490c73a8d7dfc76c88d2be1d8ea86ef86fe628242dfb0454aa67e` — FINALIZED
- transfer_with_tribute work 1: 10 GEN after reassignment (D -> R): `0xc3c6a5ee8b6c9f9fb384d4b72a435a90cc45d58763a41ea935b6ea1ac036b32a` — FINALIZED
- claim_credit work 1 by new creator (0.10 GEN): `0x5a0d7bfa6059f2fd51ce06dd16f68211798147e785580f680eef71a0539e143c` — FINALIZED
- resolve_attribution 2 (round 1) (attempt 1): `0xccde72a21c6dc86cea35c52251b15d8f56d02c637387fba0d66f15002ec14c38` — FINALIZED
- dispute_attribution 2 (4 GEN, strong counter): `0x8fa8bf98b993ad21362494696a2c95bc80abc79fa54a60406a9a67753f17b060` — FINALIZED
- resolve_attribution 2 (round 2) (attempt 1): `0xa59ca9c7e24f948a9cff3a38c7d52178202c545bba3143f55bb8bc0cf99ef286` — FINALIZED
- propose_rate work 0 -> 200bp (1 GEN): `0x9961f5e244b19953532434cb7f505ad46ea0a30f9b3b3f0c5561d375fc15b125` — FINALIZED
- resolve_rate work 0 (200bp proposal) (attempt 1): `0x7590014e8aabbd50f13ee938558feef2ad284a1c53f4d2b0ba145290d5a2a7dc` — FINALIZED
- transfer_with_tribute work 0: 10 GEN at 200bp (D -> R): `0x2961726c36b25c2ee4dd79664548d25196b322c1f816d586cd4913f502b74722` — FINALIZED
- propose_rate work 0 -> 0bp (1 GEN): `0x024c23b7cd1ef786ed6c62eef3dfce42a9da93237ef93efe30ccd46ad2700fc8` — FINALIZED
- resolve_rate work 0 (0bp proposal) (attempt 1): `0x5a6bbf4a0886bac6cb760cd78deb4f9a16e1961fcf707121ed3f2bb66b088446` — FINALIZED
- transfer_with_tribute work 0: 10 GEN at 200bp (D -> R): `0xc8e1da950534fff459ab06c7282ccaa019d6e348193f2e379070da9adc68e674` — FINALIZED
- claim_credit work 0 (0.40 GEN): `0xe9c1a405d0065f0038a02874945eb2e338e246077bf5449df910164f358cd13e` — FINALIZED
- withdraw_credit (R): `0x9ec188266dd1faa06d0464a9e7b8ad4b31ba792b0094358cef11588f14ae51a3` — FINALIZED
- withdraw_credit (A): `0x9d7f03d0bb566b719a26f40eedc413bf7a10f082e2044ed6773ff34498bf5e42` — FINALIZED
- withdraw_credit (B): `0x6f5bbf23aa7f2c5523b5a2fbe44e02325c39e82a557daa101b096b913fd75f36` — FINALIZED

## Rejected calls (all rejected before any state change; state re-read and confirmed unchanged)

- reject: deposit_funding 0 GEN — rejected at `client`: An unknown RPC error occurred.

Details: Unexpected token '<', "<!DOCTYPE "... is not valid JSON
Version: viem@2.57.17
- reject: register_work with http evidence URL — rejected at `receipt` (tx `0x2203b1b37dd93234a3c98b16ecf1d0565986afd17724df210b5dbdccd7809c75`)
- reject: withdraw_credit with no credit — rejected at `receipt` (tx `0xeb88e0ef22dbecc4e2bac89335e2be78d565acb0bb2e827db9c534d7f4552f12`)
- reject: claim_credit on missing work — rejected at `receipt` (tx `0x654e6524f8543158273e9fb882269057b16dd113201d3061919caca48f016db9`)
- reject: transfer_with_tribute 0 GEN — rejected at `receipt` (tx `0x3a5ee709bc376776c73038a831db725865b76be4d30c020b44e2ee53efa4d478`)
- reject: transfer_with_tribute to missing work — rejected at `receipt` (tx `0x0f4679633b8d8a9cd4af502657fb5f86e972cbf2231de6b9c9a46ba6d16be8d5`)
- reject: creator resolves own work — rejected at `receipt` (tx `0x3321ef3a37f3eddded9f395425928bbc0c5e11b33cff92a794445818f74345df`)
- reject: dispute_attribution before first attribution — rejected at `receipt` (tx `0x08bce15b138fb168d93299b706a9a1255f509daf034510d83adbb0ba736adea2`)
- reject: propose_rate by non-creator — rejected at `receipt` (tx `0xf7c5e2ca7e61d9c9ca6b452e48c2cf0e98975ace7056a8f211dbbe247d961467`)
- reject: propose_rate with 150bp tier — rejected at `receipt` (tx `0x332859930e62d4ab3e7d3dc984f234e44695e5f49c687cb18f8a0e328f0fd169`)
- reject: resolve_rate with no open proposal — rejected at `receipt` (tx `0x21fa6979d2f7d07f26cd2e0f43081291be236a4fce2ccd857ffa5848ed17c42f`)
- reject: claim_credit work 0 twice (nothing pending) — rejected at `receipt` (tx `0x7ce240ef3078042713019b60c11c88d20ca6f49f22253659504b3be5da0a49a9`)
- reject: claim_credit by non-creator — rejected at `receipt` (tx `0xf9619b7445f6d5ddb5b01ae0af244d5f8cfc9b59b614582e4173dbaecc978c12`)
- reject: dispute_attribution claiming the registered creator — rejected at `receipt` (tx `0xd30d3023c6ffcdad9174d949e3cf674c1c177bdad6348d44da05483e2660c637`)
- reject: dispute_attribution work 0 with 3 GEN stake (must be 4 GEN) — rejected at `receipt` (tx `0xaee1de998569f0e46cea16057f29d07bf05663d58d390d1e2db9525421a4de2b`)
- reject: dispute_attribution while a dispute is already open — rejected at `receipt` (tx `0x8a70bc90895a5228cbe2b97f8076fb9a4d080e3f508d3ce4061c503f9b3a9c17`)
- reject: propose_rate while a proposal is already open — rejected at `receipt` (tx `0xcc4617a41c53e96c428cf57ff4cf659f200b4c1f2f70e7f8da04163f1681662e`)
- reject: claim_credit work 0 twice at the end (nothing pending) — rejected at `receipt` (tx `0xf635c00fb416865f7e7bcb9b053ea280726a13a5efbeaef094ffc84400592b71`)

## Read-back (via RPC, after the flow)

- Work 0 (Neon Koi): status `CONFIRMED`, creator `0x72cb5267f8b313be2c85d4617b6c6678ba77ab50`, rate `200bp`, volume `37 GEN`, tribute earned `0.57 GEN`, final attribution `KEEP`, witnesses `1`
- Work 1 (Dust Choir): status `REASSIGNED`, creator `0x27645f863a4fbe3a6cb13707546b55d8be77125a`, rate `100bp`, volume `35 GEN`, tribute earned `0.35 GEN`, final attribution `REASSIGN`, witnesses `1`
- Work 2 (Thin Sketch): status `REASSIGNED`, creator `0x27645f863a4fbe3a6cb13707546b55d8be77125a`, rate `100bp`, volume `0 GEN`, tribute earned `0 GEN`, final attribution `REASSIGN`, witnesses `1`
- Ledger: {"total_received_wei":139000000000000000000,"total_paid_out_wei":83000000000000000000,"funding_pool_wei":56000000000000000000,"reserved_rewards_wei":0,"open_stakes_wei":0,"credits_wei":0,"pending_tribute_wei":0,"contract_balance_wei":56000000000000000000,"accounted_wei":56000000000000000000,"stray_wei":0,"invariant_ok":true}
- GEN reconciliation: {"totalReceivedGen":"139","totalPaidOutGen":"83","fundingPoolGen":"56","reservedRewardsGen":"0","openStakesGen":"0","creditsGen":"0","pendingTributeGen":"0","contractBalanceGen":"56","recipientWithdrawnGen":"71.08","creatorWithdrawnGen":"1.82","challengerWithdrawnGen":"10.10","invariantOk":true,"eoaReconciliationOk":true}
- Funding pool: {"funding_pool_wei":56000000000000000000,"dispute_stake_wei":4000000000000000000,"dispute_success_reward_wei":1000000000000000000,"rate_stake_wei":1000000000000000000,"rate_default_bp":100,"rate_tiers_bp":[0,100,200]}
- Recipient credit (after withdraw): {"address":"0xc0ff4edf7a325397cb5ae0196276282379eead2c","credit_wei":0}
- Creator credit (after withdraw): {"address":"0x72cb5267f8b313be2c85d4617b6c6678ba77ab50","credit_wei":0}
- Challenger credit (after withdraw): {"address":"0x27645f863a4fbe3a6cb13707546b55d8be77125a","credit_wei":0}
- Creator stats: {"creator":"0x72cb5267f8b313be2c85d4617b6c6678ba77ab50","works_registered":3,"tax_earned_wei":820000000000000000,"attribution_wins":1,"attribution_losses":2,"rate_proposals_approved":1,"rate_proposals_rejected":1}
- Challenger stats: {"creator":"0x27645f863a4fbe3a6cb13707546b55d8be77125a","works_registered":0,"tax_earned_wei":100000000000000000,"attribution_wins":2,"attribution_losses":1,"rate_proposals_approved":0,"rate_proposals_rejected":0}
- Leaderboard: [{"creator":"0x72cb5267f8b313be2c85d4617b6c6678ba77ab50","works_registered":3,"tax_earned_wei":820000000000000000,"attribution_wins":1,"attribution_losses":2,"rate_proposals_approved":1,"rate_proposals_rejected":1},{"creator":"0x27645f863a4fbe3a6cb13707546b55d8be77125a","works_registered":0,"tax_earned_wei":100000000000000000,"attribution_wins":2,"attribution_losses":1,"rate_proposals_approved":0,"rate_proposals_rejected":0}]
- Work count: 3
- Attribution attempts: [{"workId":0,"work":"Neon Koi","round":1,"pendingAttribution":"KEEP","status":"ATTRIBUTION_REVIEW"},{"workId":0,"work":"Neon Koi","round":2,"finalAttribution":"KEEP","status":"CONFIRMED","witnesses":[{"witness_id":"wit-0-r2","round":2,"kind":"FAILED_DISPUTE","challenger":"0x27645f863a4fbe3a6cb13707546b55d8be77125a","claimed_creator":"0x27645f863a4fbe3a6cb13707546b55d8be77125a","first_attribution":"KEEP","second_verdict":"KEEP","stake_forfeited_wei":4000000000000000000,"note":"Second evaluation agreed with the first attribution; dispute failed; 4 GEN stake forfeited to the funding pool."}],"flipped":false,"poolBeforeDisputeGen":"53","poolAfterGen":"57"},{"workId":1,"work":"Dust Choir","round":1,"pendingAttribution":"KEEP","status":"ATTRIBUTION_REVIEW"},{"workId":1,"work":"Dust Choir","round":2,"finalAttribution":"REASSIGN","status":"REASSIGNED","creator":"0x27645f863a4fbe3a6cb13707546b55d8be77125a","witnesses":[{"witness_id":"wit-1-r2","round":2,"kind":"CONTRADICTION","challenger":"0x27645f863a4fbe3a6cb13707546b55d8be77125a","claimed_creator":"0x27645f863a4fbe3a6cb13707546b55d8be77125a","first_attribution":"KEEP","first_evidence_sha256":"1be6286c4d29a5d6879bad9ddc47367ab8dd17b43007ac58d7107382637ee485","second_verdict":"REASSIGN","challenger_credit_wei":5000000000000000000,"note":"Second evaluation, reading the counter-evidence the first round never saw, disagreed with the first attribution; first attribution kept as witness only; challenger credited 4 GEN stake refund + 1 GEN reward; work reassigned."}],"flipped":true,"challengerCreditWei":5000000000000000000},{"workId":2,"work":"Thin Sketch","round":1,"pendingAttribution":"NOT_ESTABLISHED","status":"DISPUTED"},{"workId":2,"work":"Thin Sketch","round":2,"finalAttribution":"REASSIGN","status":"REASSIGNED","creator":"0x27645f863a4fbe3a6cb13707546b55d8be77125a","witnesses":[{"witness_id":"wit-2-r2","round":2,"kind":"CONTRADICTION","challenger":"0x27645f863a4fbe3a6cb13707546b55d8be77125a","claimed_creator":"0x27645f863a4fbe3a6cb13707546b55d8be77125a","first_attribution":"NOT_ESTABLISHED","first_evidence_sha256":"b8a54fa82ae772478ba8803d160cc72e6510c46e436c5d82b2927aa7f0112cfd","second_verdict":"REASSIGN","challenger_credit_wei":5000000000000000000,"note":"Second evaluation, reading the counter-evidence the first round never saw, disagreed with the first attribution; first attribution kept as witness only; challenger credited 4 GEN stake refund + 1 GEN reward; work reassigned."}],"flipped":true,"challengerCreditWei":10100000000000000000}]
- DISPUTED demonstrated on-chain: true
- Successful attribution flip on-chain: yes (work 1 flipped: true, work 2 flipped: true)
- Rate attempts: [{"workId":0,"proposedBp":200,"outcome":"APPROVE","rateBp":200,"creatorCreditBeforeWei":420000000000000000,"creatorCreditAfterWei":1420000000000000000},{"workId":0,"proposedBp":0,"outcome":"REJECT","rateBp":200}]
- Rate 200bp approved: true; rate 0bp rejected: true
- Stray GEN swept into the pool: 3 GEN (3000000000000000000 wei)
- Recipient withdrew: true; creator withdrew: true; challenger withdrew: true
- EOA balances (wei): {"funderAfterDepositWei":"9950000000000000000000","recipientBeforeWithdrawWei":"100000000000000000000","creatorBeforeWithdrawWei":"98000000000000000000","challengerBeforeWithdrawWei":"85000000000000000000","recipientAfterWithdrawWei":"171080000000000000000","creatorAfterWithdrawWei":"99820000000000000000","challengerAfterWithdrawWei":"95100000000000000000","funderFinalWei":"9885000000000000000000","evaluatorFinalWei":"93000000000000000000","freshFinalWei":"10000000000000000000"}
- EOA reconciliation (funded - sent + withdrawn == actual, per account): {"funder":{"address":"0xBe11Fb69517aAa812b2F6373f3b84CaBC3a3c79d","fundedWei":"10000000000000000000000","sentWei":"115000000000000000000","withdrawnWei":"0","expectedWei":"9885000000000000000000","actualWei":"9885000000000000000000","match":true},"creator":{"address":"0x72cB5267F8b313Be2c85d4617B6C6678ba77Ab50","fundedWei":"100000000000000000000","sentWei":"2000000000000000000","withdrawnWei":"1820000000000000000","expectedWei":"99820000000000000000","actualWei":"99820000000000000000","match":true},"challenger":{"address":"0x27645f863a4fbE3a6Cb13707546B55D8Be77125a","fundedWei":"100000000000000000000","sentWei":"15000000000000000000","withdrawnWei":"10100000000000000000","expectedWei":"95100000000000000000","actualWei":"95100000000000000000","match":true},"evaluator":{"address":"0x83E17892fc62933435085beAB35c6f6849c088dA","fundedWei":"100000000000000000000","sentWei":"7000000000000000000","withdrawnWei":"0","expectedWei":"93000000000000000000","actualWei":"93000000000000000000","match":true},"recipient":{"address":"0xC0ff4edf7a325397cB5ae0196276282379eEaD2c","fundedWei":"100000000000000000000","sentWei":"0","withdrawnWei":"71080000000000000000","expectedWei":"171080000000000000000","actualWei":"171080000000000000000","match":true},"fresh":{"address":"0x1d87b162D10FD6c3AEB2cDf024b6Edfdb1387C1E","fundedWei":"10000000000000000000","sentWei":"0","withdrawnWei":"0","expectedWei":"10000000000000000000","actualWei":"10000000000000000000","match":true}}
- Contract balance (wei): 56000000000000000000
- Local mock tests (re-run after the flow, evidence files present): 181 mock checks passed, 0 skipped (LOCAL MOCK ONLY — not on-chain evidence). 

Full machine-readable record: `evidence.json` in this repository.
