# BB84 QKD Threat Model

## System Model

The system consists of three parties and two communication channels:

- **Alice** (sender): Prepares and sends quantum states encoding key bits
- **Bob** (receiver): Measures incoming quantum states to extract key bits
- **Eve** (eavesdropper): Adversary attempting to learn the key

**Quantum channel**: Fiber-optic link carrying single photons. Untrusted — Eve has full access.

**Classical channel**: A WebRTC DataChannel (DTLS-encrypted transport) carrying basis reconciliation, error correction, and privacy amplification. BB84's security proof requires this channel to be *authenticated* — Eve may read but must not be able to modify or inject messages. **This implementation does not yet cryptographically authenticate it end-to-end**: DTLS protects the hop, but the signaling server relaying the SDP exchange is a trusted party (a malicious signaling server could in principle sit in the middle of both the DTLS session and the BB84 classical messages). What the code does enforce today: every classical message is type-checked with strict sequencing (an injected or out-of-order message aborts the round as `protocol-error`, it cannot desynchronize the protocol), array payloads are bounds-checked, and both sides independently enforce the QBER threshold. Planned next (see roadmap): a link-key MAC over the classical transcript and SDP fingerprints, plus a short-authentication-string (SAS) display, which will reduce the trusted-signaling-server assumption to "authenticated if your invite-link channel was; verified if you compared the SAS".

## What BB84 Protects Against

### Intercept-Resend Attacks

Eve intercepts each photon, measures it in a randomly chosen basis, and re-sends a new photon based on her measurement result. When Eve's basis matches Alice's, she learns the correct bit and re-sends it faithfully. When her basis doesn't match (50% of the time), she gets a random result and re-sends in the wrong state.

**Detection**: When Bob measures these re-sent photons in Alice's original basis, the bits Eve corrupted produce errors ~25% of the time. The QBER rises to approximately 25% under full intercept-resend, well above the 11% threshold.

### Individual Attacks

Eve performs independent operations on each qubit. The BB84 security proof shows that for any individual attack, the mutual information between Eve and the final key can be bounded by the QBER. Privacy amplification removes Eve's information when QBER < 11%.

**Implementation**: privacy amplification is a seeded Toeplitz hash (leftover hashing) over GF(2). Alice draws a fresh `n + m − 1`-bit seed per round from the platform CSPRNG (`crypto.getRandomValues`), transmits it over the classical channel (the seed is public — security comes from its freshness and uniformity, not its secrecy), and both sides compress the `n` corrected bits to the same `m = 128`-bit key. The parity bits disclosed during error correction are subtracted from the extractable-key budget; a round whose budget cannot cover the 128-bit target aborts (`key-budget`) instead of emitting a weakened key.

### Collective and Coherent Attacks

More powerful attacks where Eve entangles a probe with each qubit and performs a joint measurement later. The Shor-Preskill proof (2000) establishes that BB84 is secure against all attacks (including coherent attacks) when QBER < 11%, provided error correction and privacy amplification are performed correctly.

## Photon Number Splitting (PNS) Attacks

Our source uses attenuated coherent light (weak coherent pulses), not true single photons. The photon number per pulse follows a Poisson distribution with mean μ ≈ 0.1. This means:

- ~90.5% of pulses contain 0 photons (empty)
- ~9.0% contain exactly 1 photon (secure)
- ~0.5% contain 2+ photons (vulnerable to PNS)

In a PNS attack, Eve splits off one photon from multi-photon pulses and stores it in a quantum memory. After basis reconciliation, she measures her stored photons in the correct basis, learning those key bits without introducing any errors.

**Mitigation**: The low μ (0.1) minimizes multi-photon probability. The decoy-state protocol (not implemented in this simulation) would provide full protection by allowing Alice and Bob to estimate the single-photon transmission rate independently.

**Current status**: Our simulation models Poisson statistics faithfully. PNS attacks are a known limitation documented here for transparency.

## QBER Threshold Derivation

The 11% threshold comes from the information-theoretic security bound for BB84 with one-way error correction:

The key rate r per sifted bit is:
```
r = 1 - 2·h(QBER)
```

where h(p) = -p·log₂(p) - (1-p)·log₂(1-p) is the binary entropy function.

Setting r = 0 gives the maximum tolerable QBER:
```
1 - 2·h(QBER_max) = 0
h(QBER_max) = 0.5
QBER_max ≈ 0.11 (11%)
```

Above 11%, privacy amplification cannot guarantee that Eve has negligible information about the final key.

## System Assumptions

1. **Trusted devices**: Alice's source and Bob's detectors are not compromised. There is no detector blinding, Trojan horse attacks on the source, or other device-level attacks. (Device-independent QKD would relax this assumption but is not implemented.)

2. **Authenticated classical channel**: *assumed, not yet implemented end-to-end* — see the System Model note above. The DataChannel hop is DTLS-protected and the message layer is strictly typed and sequenced, but authentication currently rests on trusting the signaling server that brokered the connection. A MITM on the classical channel breaks the protocol regardless of quantum security, which is why channel authentication (MAC + SAS) is the next planned change rather than a footnote.

3. **No side channels**: The implementation does not leak key material through timing, power consumption, electromagnetic emissions, or other side channels.

4. **Random number generation**: key bits, basis choices, and the Toeplitz seed are drawn from the platform CSPRNG (`crypto.getRandomValues`). The simulated channel's physics (photon loss, wrong-basis measurement outcomes) deliberately uses a plain PRNG — it models nature, not secrets.

## Known Limitations

1. **Simulation only**: The quantum channel is simulated, not physically secure. The security guarantees of BB84 rely on the laws of quantum mechanics; a software simulation provides the protocol logic and statistics but not the physical security.

2. **No decoy states**: The simulation does not implement the decoy-state protocol (Lo, Ma, Chen 2005), which is required for security with weak coherent pulse sources against PNS attacks. This is documented as future work.

3. **Simplified error correction**: the implementation is a single pass of 8-bit block parities, not Cascade — a mismatched block flips its first bit, so blocks with an even number of errors (or errors past the first position) can leave residual errors that surface as a failed round rather than being corrected. The disclosed parity bits are subtracted from the key budget (see above), but full Cascade (multi-pass binary search, as specified in `docs/diagrams/bb84-protocol.puml`) and lower-leakage codes (e.g. LDPC) remain future work.

3a. **Non-random QBER sample**: the QBER estimate uses the first `min(⌊sifted/4⌋, 256)` sifted positions rather than a randomly chosen subset. Against the modeled intercept-resend attack (which is position-independent) this estimates the same rate; an adversary who could target positions would evade it, so a production system must sample randomly.

4. **No finite-key effects**: The security analysis assumes asymptotic key lengths. For short keys (as in our simulation with 4096 raw bits), finite-key corrections reduce the secure key rate. A production system would need composable security bounds.

5. **Static channel model**: The simulation uses fixed channel parameters. Real fiber channels have time-varying loss and noise characteristics.

## Attack Surface

This table describes what the code actually does — every mitigation listed here
is implemented and tested, and the residual risks are stated rather than
papered over.

| Component | Risk | Mitigation (implemented) | Residual risk |
|-----------|------|--------------------------|---------------|
| Signaling: connect/create/join | Flooding, room squatting | Per-IP token bucket (30/min default, `QVC_RATE_LIMIT`); connections over the cap are refused | In-memory, per-process; resets on restart |
| Room access | Uninvited joiners | Room ids are ~128-bit `secrets.token_urlsafe` capability tokens carried in the invite link's URL fragment; join errors don't echo tokens; dashboards/logs only ever see redacted prefixes | Anyone holding the link can join — the link is the credential; share it over a channel you trust |
| `/admin/*` endpoints | Recon (rooms, sids), unauthorized ops | Fail-closed shared secret (`QVC_ADMIN_SECRET`, constant-time compare, 404 when unset or wrong); responses redact sids and room ids regardless | Secret distribution is out of band |
| Media frames | Plaintext leak before/without a key | Fail-closed crypto worker: frames are **dropped** (never passed through) when no key is installed, on short/malformed frames, and on GCM auth failure; a mid-call renegotiation offer is ignored rather than rebuilding a keyless worker; the UI pill shows worker-reported state (amber/green/red) | A user can read the red "NOT ENCRYPTED" pill and choose to keep waiting; no media flows either way |
| Key material in memory | Memory dump | Keys live only in the crypto worker as non-extractable WebCrypto `CryptoKey`s; a new BB84 round re-keys when the key budget runs low (key index increments per round) | No fixed wall-clock rotation interval; a call that never exhausts its budget keeps its key for the call's duration |
| Classical channel | MITM, injection | Typed + sequenced message layer (injection ⇒ clean abort), bounds-checked payloads, both-side QBER enforcement; DataChannel mux drops malformed JSON/unknown channels and caps buffers | End-to-end authentication pending (MAC + SAS, see System Model) |
| Eavesdropper toggle | Misread as a real attack control | It is a **local demo control**: the room creator's client injects intercept-resend into its own *simulated* quantum channel so viewers can watch the QBER spike. It is not an admin feature and grants nothing over a real channel | None — it only degrades the toggler's own session |
| Third-party script | Supply-chain (CDN) | socket.io-client is vendored into the repo (provenance hash recorded in `index.html`); no runtime third-party script loads | Vendored copy must be bumped manually for security releases |
| Configuration | Parameter tampering | Environment variables are local-only; CORS origins are exact strings or fully anchored regexes (prefix-attack origins like `localhostevil.com` are rejected, with regression tests) | — |

**Historical note — `key.bin`**: earlier revisions of this repository wrote a
`key.bin` file from a prototype key-persistence experiment. It was never used
to protect live traffic, the code path is gone, and the filename remains in
`.gitignore` only to keep stray copies out of version control. Treat any
`key.bin` found in old checkouts as dead material: delete it; do not reuse it.

## References

1. Bennett, C. H., & Brassard, G. (1984). "Quantum cryptography: Public key distribution and coin tossing." Proceedings of IEEE International Conference on Computers, Systems and Signal Processing.
2. Shor, P. W., & Preskill, J. (2000). "Simple proof of security of the BB84 quantum key distribution protocol." Physical Review Letters, 85(2), 441.
3. Lo, H. K., Ma, X., & Chen, K. (2005). "Decoy state quantum key distribution." Physical Review Letters, 94(23), 230504.
4. Brassard, G., & Salvail, L. (1993). "Secret-key reconciliation by public discussion." Advances in Cryptology — EUROCRYPT '93.
