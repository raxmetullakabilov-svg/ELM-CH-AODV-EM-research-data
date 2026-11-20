# Data dictionary (key columns)

All files are UTF-8 CSV with first-row headers.

* `Scenario` / `scenario`: LOW, NOMINAL or STRESS joint operating condition.
* `Seed` / `seed`: realization identifier; STRESS seed 110 was not used.
* `Protocol` / `protocol`: ELM\_CH\_AODV\_EM, AODV, AODV\_EM or AOMDV.
* `Variant`: FULL, NO\_HSRD, NO\_EMLQ, NO\_DGPS or NO\_AHLR.
* `PDR`: application-packet delivery ratio (unit interval).
* `meanE2EDelay\_s` / `Delay`: mean end-to-end delay over delivered packets, seconds.
* `NRL\_P`: routing transmissions normalized by delivered data packets.
* `NRL\_B`: routing payload bytes normalized by delivered data bytes.
* `energyPerDeliveredBit\_J` / `Ebit`: communication-only energy per delivered bit in J/bit.
* `FRPDR`: fusion-ready *surrogate* delivery ratio over generated complete observation pairs, at 200-ms per-component deadline and 50-ms network-delay skew threshold.
* `SourceType`, `scientificSourceHash`, `scenarioFingerprint`: provenance/diagnostic labels; the H600 legacy checksum is sensitive to floating-point reduction order and is not a cryptographic content hash.

`statistics/` are provided as frozen original outputs, rather than recomputed/overwritten in this release.

