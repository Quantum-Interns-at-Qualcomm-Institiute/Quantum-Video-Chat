# BB84 QKD Threat Model

## System Model

The system consists of three parties and two communication channels:

- **Alice** (sender): Prepares and sends quantum states encoding key bits
- **Bob** (receiver): Measures incoming quantum states to extract key bits
- **Eve** (eavesdropper): Adversary attempting to learn the key

**Quantum channel**: Fiber-optic link carrying single photons. Untrusted — Eve has full access.

**Classical channel**: Authenticated TCP/TLS connection for basis reconciliation, error correction, and privacy amplification. Assumed authenticated but not secret — Eve can read but not modify messages.

## What BB84 Protects Against

### Intercept-Resend Attacks

Eve intercepts each photon, measures it in a randomly chosen basis, and re-sends a new photon based on her measurement result. When Eve's basis matches Alice's, she learns the correct bit and re-sends it faithfully. When her basis doesn't match (50% of the time), she gets a random result and re-sends in the wrong state.

**Detection**: When Bob measures these re-sent photons in Alice's original basis, the bits Eve corrupted produce errors ~25% of the time. The QBER rises to approximately 25% under full intercept-resend, well above the 11% threshold.

### Individual Attacks

Eve performs independent operations on each qubit. The BB84 security proof shows that for any individual attack, the mutual information between Eve and the final key can be bounded by the QBER. Privacy amplification removes Eve's information when QBER < 11%.

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

2. **Authenticated classical channel**: The TCP/TLS connection between Alice and Bob is authenticated. Eve cannot modify classical messages (man-in-the-middle on the classical channel would break the protocol regardless of quantum security).

3. **No side channels**: The implementation does not leak key material through timing, power consumption, electromagnetic emissions, or other side channels.

4. **Random number generation**: Basis and bit selection use cryptographically secure random number generators (numpy's default_rng with system entropy).

## Known Limitations

1. **Simulation only**: The quantum channel is simulated, not physically secure. The security guarantees of BB84 rely on the laws of quantum mechanics; a software simulation provides the protocol logic and statistics but not the physical security.

2. **No decoy states**: The simulation does not implement the decoy-state protocol (Lo, Ma, Chen 2005), which is required for security with weak coherent pulse sources against PNS attacks. This is documented as future work.

3. **Simplified error correction**: The Cascade protocol implementation is simplified. Production systems use more efficient protocols (e.g., LDPC codes) with lower information leakage.

4. **No finite-key effects**: The security analysis assumes asymptotic key lengths. For short keys (as in our simulation with 4096 raw bits), finite-key corrections reduce the secure key rate. A production system would need composable security bounds.

5. **Static channel model**: The simulation uses fixed channel parameters. Real fiber channels have time-varying loss and noise characteristics.

## Attack Surface

| Component | Risk | Mitigation |
|-----------|------|------------|
| REST API (:5050) | DoS, unauthorized access | Rate limiting (30 req/min per IP) |
| WebSocket (:3000) | Session hijacking | User ID authentication on connect |
| Key material in memory | Memory dump | Keys rotate every 1-3 seconds; old keys are dereferenced |
| Configuration | Parameter tampering | Environment variables and INI files are local-only |
| Eavesdropper toggle | Demo feature abuse | Admin endpoint only; not exposed to clients |
| Classical channel | MITM | TLS with certificate pinning (when certs are configured) |

## References

1. Bennett, C. H., & Brassard, G. (1984). "Quantum cryptography: Public key distribution and coin tossing." Proceedings of IEEE International Conference on Computers, Systems and Signal Processing.
2. Shor, P. W., & Preskill, J. (2000). "Simple proof of security of the BB84 quantum key distribution protocol." Physical Review Letters, 85(2), 441.
3. Lo, H. K., Ma, X., & Chen, K. (2005). "Decoy state quantum key distribution." Physical Review Letters, 94(23), 230504.
4. Brassard, G., & Salvail, L. (1993). "Secret-key reconciliation by public discussion." Advances in Cryptology — EUROCRYPT '93.
