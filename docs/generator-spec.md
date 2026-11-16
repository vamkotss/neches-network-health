# Generator specification

The generator produces synthetic telemetry plus answer keys. Everything is seeded, so the same seed gives byte-identical output.

## Determinism

- Default seed: 20261116, set in config and overridable from the command line.
- All randomness comes from one numpy generator created from the seed.
- A test runs the generator twice with the same seed and compares the output.

## Time window and scale

- Window starts 2026-11-01T00:00:00Z and lasts 14 days.
- One reading per device every 5 minutes, so 4,032 readings per device.
- Default dev scale: 500 devices (5 OLTs x 5 PON ports x 20 devices). About 2 million rows.
- Full scale: 2,000 devices (25 OLTs x 4 PON ports x 20 devices). About 8 million rows.
- Test scale: 50 devices for 1 day.

## Healthy baseline per device

| Field | Rule |
|---|---|
| rx_power_dbm | Per-device base drawn from Normal(-19, 1.5), clipped to [-24, -12], plus per-reading noise Normal(0, 0.3) |
| tx_power_dbm | Normal(2.5, 0.3) |
| fec_corrected | Poisson(20) |
| fec_uncorrected | Poisson(0.01) |
| bip_errors | Poisson(2) |
| latency_ms | Lognormal around 8 ms |
| packet_loss_pct | Small value around 0.01, never below 0 |
| temperature_c | Daily sine wave between 35 and 55 |
| firmware | "2.4.1" at the start |

## Planted behaviors

Rates are shares of the fleet. Counts are rounded, and the answer keys are the source of truth.

| Behavior | Rule | Answer key |
|---|---|---|
| Slow degradation | 3% of devices. rx_power_dbm falls 0.5 dB per day from a random start day, and fec_uncorrected rises with the drift. | degradation_events.csv |
| Single-device outage | 1.5% of devices. No readings for 20 to 180 minutes. | outage_events.csv |
| Shared-fiber outage | 1 in 5 PON ports. All 20 devices on the port go silent together for 30 to 240 minutes. | outage_events.csv |

## Planted defects

| # | Defect | Rule | Answer key |
|---|---|---|---|
| 1 | Duplicate events | 1.5% of rows are repeated 1 to 2 times, in the same or a later batch | planted_defects.csv |
| 2 | Late events | 4% of rows arrive 1 to 6 hours after event_ts, in a later batch | planted_defects.csv |
| 3 | Clock skew | 1% of devices report event_ts 37 minutes behind real time for the whole window | planted_defects.csv |
| 4 | Unit change | 15% of devices upgrade from firmware 2.4.1 to 2.5.0 on day 8 at a random time. After the upgrade, rx_power_dbm and tx_power_dbm hold milliwatt values (for example 0.0126), not dBm. | planted_defects.csv |
| 5 | Silent device | 0.6% of devices stop reporting for 6 to 36 hours with no outage record, then resume | planted_defects.csv |

## Output

- Telemetry: JSON lines files, gzip compressed, one file per hour of arrival time.
- Path: landing/telemetry/dt=YYYY-MM-DD/hour=HH/batch_NNNN.jsonl.gz
- Row fields: device_id, event_ts, rx_power_dbm, tx_power_dbm, fec_corrected, fec_uncorrected, bip_errors, latency_ms, packet_loss_pct, temperature_c, firmware.
- Ingest metadata (ingest_ts, source file) is added later by Bronze, not by the generator.
- Devices table: devices.csv with device_id, olt_id, pon_port, region, model, install_date.
- Answer keys go in a separate ground_truth folder: outage_events.csv, degradation_events.csv, planted_defects.csv.

## Tests that must exist before the generator is considered done

1. Same seed twice gives identical output.
2. Row count equals devices x 4,032 minus rows removed for outages and silent periods, plus duplicates.
3. Every planted defect appears in planted_defects.csv, and the counts match what the files actually contain.
4. After the unit change, affected rows really hold values between 0 and 1.
5. No output file or log contains a real company name.
