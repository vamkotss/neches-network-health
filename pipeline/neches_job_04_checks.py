# Databricks notebook source
# Import helper functions (F) and tools for timestamps
from datetime import UTC, datetime

from pyspark.sql import functions as F

# The S3 bucket that holds the project files
BUCKET = "s3://neches-network-health-vamsi-2711"

# Load the tables we want to check
bronze = spark.table("workspace.neches.bronze_telemetry")
silver = spark.table("workspace.neches.silver_telemetry")

# The official list of devices, from the reference file
expected_devices = spark.read.option("header", True).csv(f"{BUCKET}/reference/devices.csv").count()

# Measure everything we want to check
bronze_n = bronze.count()
silver_n = silver.count()
silver_devices = silver.select("device_id").distinct().count()

# Readings that appear more than once for the same device and time
dupes = silver.groupBy("device_id", "event_ts").count().filter("count > 1").count()

# Readings that are missing a device id or a timestamp
null_keys = silver.filter(F.col("device_id").isNull() | F.col("event_ts").isNull()).count()

# Readings that do not sit on a 5-minute mark
off_grid = silver.filter((F.minute("event_ts") % 5 != 0) | (F.second("event_ts") != 0)).count()

# Receive power must be between -40 and 0 dBm (isnan catches broken conversions)
bad_rx = silver.filter(
    F.isnan("rx_power_dbm") | (F.col("rx_power_dbm") < -40) | (F.col("rx_power_dbm") > 0)
).count()

# Transmit power must be between -5 and 10 dBm
bad_tx = silver.filter(
    F.isnan("tx_power_dbm") | (F.col("tx_power_dbm") < -5) | (F.col("tx_power_dbm") > 10)
).count()

# Each check is: (name, passed?, detail text)
checks = [
    ("bronze_not_empty", bronze_n > 0, f"bronze rows = {bronze_n}"),
    (
        "silver_not_larger_than_bronze",
        silver_n <= bronze_n,
        f"silver {silver_n} vs bronze {bronze_n}",
    ),
    ("no_duplicate_readings", dupes == 0, f"duplicate readings = {dupes}"),
    ("no_null_keys", null_keys == 0, f"rows missing a key = {null_keys}"),
    ("timestamps_on_5_minute_grid", off_grid == 0, f"off-grid readings = {off_grid}"),
    ("rx_power_plausible", bad_rx == 0, f"implausible rx readings = {bad_rx}"),
    ("tx_power_plausible", bad_tx == 0, f"implausible tx readings = {bad_tx}"),
    (
        "all_devices_present",
        silver_devices == expected_devices,
        f"silver devices {silver_devices} vs expected {expected_devices}",
    ),
]

# Save this run's results to a table, with the time of the run
run_ts = datetime.now(UTC)
rows = [(run_ts, name, passed, detail) for name, passed, detail in checks]
results = spark.createDataFrame(
    rows, "run_ts timestamp, check_name string, passed boolean, detail string"
)
results.write.mode("append").saveAsTable("workspace.neches.gold_quality_checks")

# Show this run's results
display(results)

# If any check failed, stop the job with a clear error message
failed = [name for name, passed, _ in checks if not passed]
if failed:
    raise RuntimeError(f"Data quality checks failed: {failed}")
print("All data quality checks passed")

# COMMAND ----------
