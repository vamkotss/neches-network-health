# Databricks notebook source
# Import Spark's helper functions (F) and the window tool for ranking rows
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Use UTC for all times
spark.conf.set("spark.sql.session.timeZone", "UTC")

# Table names: where we read from and where we write to
BRONZE = "workspace.neches.bronze_telemetry"
SILVER = "workspace.neches.silver_telemetry"

# The known size of the clock error on skewed devices: their clocks run 37 minutes behind
SKEW_MINUTES = 37

# Load the raw Bronze table
bronze = spark.table(BRONZE)

# Step 1: turn text into real timestamps and read the arrival time from the file path
parsed = (
    bronze
    .withColumn("event_ts", F.to_timestamp("event_time"))
    .withColumn("_dt", F.regexp_extract("_source_file", r"dt=(\d{4}-\d{2}-\d{2})", 1))
    .withColumn("_hour", F.regexp_extract("_source_file", r"hour=(\d{2})", 1))
    .withColumn(
        "arrival_ts",
        F.to_timestamp(F.concat(F.col("_dt"), F.lit(" "), F.col("_hour"), F.lit(":00:00"))),
    )
)

# Step 2: keep only the first copy of each reading (same device and same event time)
window = Window.partitionBy("device_id", "event_ts").orderBy("arrival_ts", "_source_file")
deduped = (
    parsed
    .withColumn("_rn", F.row_number().over(window))
    .filter(F.col("_rn") == 1)
    .drop("_rn", "_dt", "_hour")
)

# Step 3: find devices with a skewed clock
# A healthy reading lands on a 5-minute mark (12:00, 12:05, ...). Off-grid means a wrong clock.
is_off_grid = (F.minute("event_ts") % 5 != 0) | (F.second("event_ts") != 0)
share = (
    deduped.withColumn("off_grid", is_off_grid.cast("int"))
    .groupBy("device_id")
    .agg(F.avg("off_grid").alias("off_grid_share"))
)
# A device is skewed when more than 90% of its readings are off-grid
skewed_ids = [r.device_id for r in share.filter(F.col("off_grid_share") > 0.9).collect()]

# Step 4: fix units and clocks, and recompute how late each reading was
silver = (
    deduped
    # Firmware 2.5.0 reports power in milliwatts instead of dBm
    .withColumn("unit_converted", F.col("firmware") == "2.5.0")
    # dBm = 10 * log10(milliwatts); applied only to the marked rows
    .withColumn(
        "rx_power_dbm",
        F.when(F.col("unit_converted"), 10 * F.log10(F.col("rx_power_dbm"))).otherwise(F.col("rx_power_dbm")),
    )
    .withColumn(
        "tx_power_dbm",
        F.when(F.col("unit_converted"), 10 * F.log10(F.col("tx_power_dbm"))).otherwise(F.col("tx_power_dbm")),
    )
    # Mark every reading from a skewed device
    .withColumn("clock_corrected", F.col("device_id").isin(skewed_ids))
    # Add the missing minutes back to the off-grid readings of those devices
    .withColumn(
        "event_ts",
        F.when(
            F.col("clock_corrected") & is_off_grid,
            F.col("event_ts") + F.expr(f"INTERVAL {SKEW_MINUTES} MINUTES"),
        ).otherwise(F.col("event_ts")),
    )
    # Minutes between the reading and its arrival (positive = arrived late)
    .withColumn(
        "arrival_delay_min",
        (F.unix_timestamp("arrival_ts") - F.unix_timestamp("event_ts")) / 60,
    )
)

# Save Silver (replaces the old table, so re-running always gives the same result)
silver.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(SILVER)

# Print a summary so the job log shows what happened
final = spark.table(SILVER)
print("Silver rows:", final.count())
print("Skewed devices fixed:", len(skewed_ids))
print("Devices with converted units:", final.filter("unit_converted").select("device_id").distinct().count())
print("Off-grid readings left:", final.filter(is_off_grid).count())

# COMMAND ----------
