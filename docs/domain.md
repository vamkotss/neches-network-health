# Domain primer: fiber access networks

These are design assumptions for a synthetic project, loosely based on typical GPON fiber networks.

## The picture

Think of a water system.

- **OLT** (optical line terminal): the pumping station at the provider's building.
- **Fiber and splitters**: the pipes and branches. One OLT port feeds many homes through passive splitters.
- **ONT** (optical network terminal): the tap at the customer's home. Each ONT reports telemetry about its own connection.

A fault on the shared fiber hurts many customers at once. A fault on one home's drop cable hurts one customer.

## Signals each ONT reports

| Signal | Meaning |
|---|---|
| rx_power_dbm | Light received at the home. More negative means weaker. |
| tx_power_dbm | Light the ONT sends back upstream. |
| fec_corrected | Errors the system fixed on its own. A rise is an early warning. |
| fec_uncorrected | Errors that lost data. A rise means customers feel it. |
| bip_errors | A separate count of bit errors on the link. |
| latency_ms | Round-trip delay. |
| packet_loss_pct | Share of packets that never arrive. |
| temperature_c | Device temperature. |

## Reading dBm

dBm is a logarithmic scale. Every 3 dB drop halves the light. Negative numbers are normal: -20 is stronger than -26.

## Design thresholds for rx_power_dbm

| State | Range |
|---|---|
| Healthy | -8 to -25 |
| Warning | below -25 down to -27 |
| Critical | below -27 |

## The story we want to detect

A slow drift in rx_power_dbm, then rising fec_uncorrected, then customer complaints days later. The pipeline should flag the drift early.

## Why real telemetry is messy

Collectors send data in batches. Retries create duplicates. Network delays create late arrivals. Device clocks drift. Firmware updates change units. Devices go silent. Each of these becomes a planted defect in this project.
