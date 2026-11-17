# Databricks notebook source
# Import Spark's helper functions (F) and the window tool for ranking rows
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Make all timestamps use UTC, so times are not shifted by a local time zone
spark.conf.set("spark.sql.session.timeZone", "UTC")

# Load the raw Bronze table
bronze = spark.table("workspace.neches.bronze_telemetry")

# Step 1: turn text into real timestamps and read the arrival time from the file path
parsed = (
    bronze
    # Convert the text event_time (like 2026-11-01T03:05:00Z) into a real timestamp
    .withColumn("event_ts", F.to_timestamp("event_time"))
    # Pull the date out of the file path (the dt=YYYY-MM-DD part)
    .withColumn("_dt", F.regexp_extract("_source_file", r"dt=(\d{4}-\d{2}-\d{2})", 1))
    # Pull the hour out of the file path (the hour=HH part)
    .withColumn("_hour", F.regexp_extract("_source_file", r"hour=(\d{2})", 1))
    # Combine date and hour into the time the file arrived
    .withColumn(
        "arrival_ts",
        F.to_timestamp(F.concat(F.col("_dt"), F.lit(" "), F.col("_hour"), F.lit(":00:00"))),
    )
    # How many minutes late the row was (arrival time minus event time)
    .withColumn(
        "arrival_delay_min",
        (F.unix_timestamp("arrival_ts") - F.unix_timestamp("event_ts")) / 60,
    )
)

# Step 2: rank copies of the same reading (same device + same event time), earliest arrival first
window = Window.partitionBy("device_id", "event_ts").orderBy("arrival_ts", "_source_file")

# Keep only the first copy of each reading and drop the helper column
deduped = (
    parsed.withColumn("_rn", F.row_number().over(window))
    .filter(F.col("_rn") == 1)
    .drop("_rn", "_dt", "_hour")
)

# Save the result as the Silver table (replaces it if you run this again)
deduped.write.mode("overwrite").saveAsTable("workspace.neches.silver_telemetry")

# Print how many rows each layer has
print("Bronze rows:", bronze.count())
print("Silver rows:", spark.table("workspace.neches.silver_telemetry").count())

# COMMAND ----------

# Read the answer key the generator wrote, from the S3 ground_truth folder
BUCKET = "s3://neches-network-health-vamsi-2711"
key = spark.read.option("header", True).csv(f"{BUCKET}/ground_truth/planted_defects.csv")

# Show how many defects of each type were planted
display(key.groupBy("defect_type").count().orderBy("defect_type"))

# COMMAND ----------

# Compare the signal columns for each firmware version
# If the unit change is real, firmware 2.5.0 will show tiny positive numbers (milliwatts)
# while firmware 2.4.1 shows negative numbers (dBm)
display(
    spark.table("workspace.neches.silver_telemetry")
    .groupBy("firmware")
    .agg(
        # Number of rows
        F.count("*").alias("rows"),
        # Number of different devices
        F.countDistinct("device_id").alias("devices"),
        # Lowest, average and highest receive power
        F.min("rx_power_dbm").alias("rx_min"),
        F.avg("rx_power_dbm").alias("rx_avg"),
        F.max("rx_power_dbm").alias("rx_max"),
        # Same for transmit power, to check whether it changed too
        F.min("tx_power_dbm").alias("tx_min"),
        F.avg("tx_power_dbm").alias("tx_avg"),
        F.max("tx_power_dbm").alias("tx_max"),
    )
)

# COMMAND ----------

# Mark the rows that use the new unit: firmware 2.5.0 reports power in milliwatts (mW)
fixed = deduped.withColumn("unit_converted", F.col("firmware") == "2.5.0")

# Convert receive power from milliwatts back to dBm, only for the marked rows
# dBm = 10 * log10(milliwatts)
fixed = fixed.withColumn(
    "rx_power_dbm",
    F.when(F.col("unit_converted"), 10 * F.log10(F.col("rx_power_dbm"))).otherwise(
        F.col("rx_power_dbm")
    ),
)

# Do the same for transmit power
fixed = fixed.withColumn(
    "tx_power_dbm",
    F.when(F.col("unit_converted"), 10 * F.log10(F.col("tx_power_dbm"))).otherwise(
        F.col("tx_power_dbm")
    ),
)

# Save as the Silver table again (replace the old one; allow the new unit_converted column)
(
    fixed.write.mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("workspace.neches.silver_telemetry")
)

# Check: both firmware groups should now show rx around -19 and tx around 2.5
display(
    spark.table("workspace.neches.silver_telemetry")
    .groupBy("firmware")
    .agg(
        F.count("*").alias("rows"),
        F.countDistinct("device_id").alias("devices"),
        F.avg("rx_power_dbm").alias("rx_avg"),
        F.avg("tx_power_dbm").alias("tx_avg"),
    )
)

# COMMAND ----------

# Load the current Silver table
silver_now = spark.table("workspace.neches.silver_telemetry")

# Mark each reading as "off the grid" when its minute is not a multiple of 5 or its seconds are not zero
checked = silver_now.withColumn(
    "off_grid",
    (F.minute("event_ts") % 5 != 0) | (F.second("event_ts") != 0),
)

# For each device, count how many of its readings are off the grid
off_grid_devices = (
    checked.groupBy("device_id")
    .agg(
        F.count("*").alias("rows"),
        F.sum(F.col("off_grid").cast("int")).alias("off_grid_rows"),
    )
    # Keep only devices that have at least one off-grid reading
    .filter(F.col("off_grid_rows") > 0)
    .orderBy(F.desc("off_grid_rows"))
)

# Show those devices
display(off_grid_devices)

# COMMAND ----------


# COMMAND ----------

# Reload the full answer key, then show only the clock-skew rows
BUCKET = "s3://neches-network-health-vamsi-2711"
key_all = spark.read.option("header", True).csv(f"{BUCKET}/ground_truth/planted_defects.csv")
display(key_all.filter(F.col("defect_type") == "clock_skew"))

# COMMAND ----------

# Print the full clock-skew notes from the answer key, one line per device
skew_rows = key_all.filter(F.col("defect_type") == "clock_skew").collect()
for r in skew_rows:
    print(r.device_id, "->", r.detail)

# The 5 skewed device ids
skewed_ids = [r.device_id for r in skew_rows]

# Show the first and last reading time for each skewed device
# A healthy device starts at 2026-11-01 00:00:00 and ends at 2026-11-14 23:55:00
display(
    silver_now.filter(F.col("device_id").isin(skewed_ids))
    .groupBy("device_id")
    .agg(F.min("event_ts").alias("first_reading"), F.max("event_ts").alias("last_reading"))
)

# COMMAND ----------

# Load the current Silver table
current = spark.table("workspace.neches.silver_telemetry")

# A reading is "off the grid" if its minute is not a multiple of 5 or its seconds are not zero
is_off_grid = (F.minute("event_ts") % 5 != 0) | (F.second("event_ts") != 0)

# For each device, the share of its readings that are off the grid
share = (
    current.withColumn("off_grid", is_off_grid.cast("int"))
    .groupBy("device_id")
    .agg(F.avg("off_grid").alias("off_grid_share"))
)

# Devices where almost every reading is off the grid have a wrong clock
detected_ids = [r.device_id for r in share.filter(F.col("off_grid_share") > 0.9).collect()]
print("Devices detected with a skewed clock:", sorted(detected_ids))

# The fix applies only to off-grid readings of those devices (so re-running is safe)
needs_fix = F.col("device_id").isin(detected_ids) & is_off_grid

corrected = (
    current
    # Mark all readings of the skewed devices
    .withColumn("clock_corrected", F.col("device_id").isin(detected_ids))
    # Their clocks ran 37 minutes behind, so add 37 minutes back
    .withColumn(
        "event_ts",
        F.when(needs_fix, F.col("event_ts") + F.expr("INTERVAL 37 MINUTES")).otherwise(
            F.col("event_ts")
        ),
    )
    # Recalculate how late each reading was, now that the event time is right
    .withColumn(
        "arrival_delay_min",
        (F.unix_timestamp("arrival_ts") - F.unix_timestamp("event_ts")) / 60,
    )
)

# Save the corrected Silver table
(
    corrected.write.mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("workspace.neches.silver_telemetry")
)

# Check 1: no off-grid readings should remain (expect 0)
final = spark.table("workspace.neches.silver_telemetry")
print("Off-grid readings left:", final.filter(is_off_grid).count())

# Check 2: the devices we detected should match the answer key's 5 devices (expect True)
print("Matches the answer key:", set(detected_ids) == set(skewed_ids))

# Check 3: first and last reading for the corrected devices (expect 00:00 and 23:55)
display(
    final.filter(F.col("clock_corrected"))
    .groupBy("device_id")
    .agg(F.min("event_ts").alias("first_reading"), F.max("event_ts").alias("last_reading"))
)

# COMMAND ----------
