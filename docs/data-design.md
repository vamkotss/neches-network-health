# Data design

## Scale

2,000 devices, one reading every 5 minutes, 14 days. That is about 8 million telemetry rows.

## Source tables (synthetic)

| Table | Grain | Key columns |
|---|---|---|
| devices | one row per ONT | device_id, olt_id, pon_port, region, model, install_date |
| telemetry | one row per ONT per 5 minutes | device_id, event_ts, rx_power_dbm, tx_power_dbm, fec_corrected, fec_uncorrected, bip_errors, latency_ms, packet_loss_pct, temperature_c, firmware |
| outage_events | one row per true outage (ground truth) | device_id, start_ts, end_ts, cause |

The outage_events table is the answer key. It lets us test whether the pipeline finds what we planted.

## Landing format

JSON lines files, written in batches to a path like:

    landing/telemetry/dt=2026-11-16/hour=09/batch_0001.jsonl

## Planted defects

| # | Defect | How it shows up | How the pipeline handles it |
|---|---|---|---|
| 1 | Duplicate events | Same device_id and event_ts appears more than once | Deduplicate on (device_id, event_ts) in Silver |
| 2 | Late events | Rows arrive hours after event_ts | Use event time with a watermark, keep ingest_ts for audit |
| 3 | Clock skew | One device's event_ts runs behind real time | Detect by comparing event_ts with arrival time, flag the device |
| 4 | Unit change | After a firmware version, power is reported in milliwatts, not dBm | Detect by firmware and value range, convert with 10 * log10(mW) |
| 5 | Silent device | A device stops reporting with no outage record | Detect gaps longer than 15 minutes, raise a heartbeat alert |

## Layers

- **Bronze**: raw files as they arrived, plus ingest_ts and source file name.
- **Silver**: deduplicated, units normalized, timestamps validated.
- **Gold**: device_health_daily (score per device per day), degradation_alerts (drift plus error rise), outage_windows (detected outages), kpi_daily (fleet-level summary).

## Success checks

- Silver has no duplicate (device_id, event_ts) pairs.
- All power values are in dBm after normalization.
- Detected outages match outage_events within a stated tolerance.
- Every planted defect has at least one test proving it is caught.
