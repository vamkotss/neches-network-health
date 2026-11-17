# Databricks notebook source
# Import Spark's helper functions (F)
from pyspark.sql import functions as F

# Use UTC for all times
spark.conf.set("spark.sql.session.timeZone", "UTC")

# Load the cleaned Silver table
silver = spark.table("workspace.neches.silver_telemetry")

# Convert each reading's time into "days since the data started" (Nov 1, 2026)
with_days = silver.withColumn(
    "day_num",
    (F.unix_timestamp("event_ts") - F.unix_timestamp(F.lit("2026-11-01 00:00:00"))) / 86400,
)

# For each device, fit a straight line through its receive power over time
# regr_slope gives how many dB the signal changes per day (negative = getting weaker)
trend = with_days.groupBy("device_id").agg(
    F.regr_slope("rx_power_dbm", "day_num").alias("rx_slope_db_per_day"),
    F.avg("rx_power_dbm").alias("rx_avg_dbm"),
    F.min("rx_power_dbm").alias("rx_min_dbm"),
    F.count("*").alias("readings"),
)

# Flag a device as degrading if its signal drops by more than 0.05 dB per day
flagged = trend.withColumn("is_degrading", F.col("rx_slope_db_per_day") <= -0.05)

# Save the result as a Gold table
flagged.write.mode("overwrite").saveAsTable("workspace.neches.gold_device_trend")

# Show the 20 steepest drops first
display(
    spark.table("workspace.neches.gold_device_trend")
    .orderBy("rx_slope_db_per_day")
    .limit(20)
)

# COMMAND ----------

# Read the answer key of devices that were really degraded on purpose
BUCKET = "s3://neches-network-health-vamsi-2711"
key = spark.read.option("header", True).csv(f"{BUCKET}/ground_truth/degradation_events.csv")

# Devices that truly were degraded, and devices our pipeline flagged
planted = key.select("device_id").distinct()
detected = spark.table("workspace.neches.gold_device_trend").filter("is_degrading").select("device_id")

# Compare the two lists
planted_n = planted.count()
detected_n = detected.count()
correct_n = detected.join(planted, "device_id").count()

print("Planted (truth):", planted_n)
print("Detected by pipeline:", detected_n)
print("Correctly found:", correct_n)
print("Missed:", planted_n - correct_n)
print("False alarms:", detected_n - correct_n)

# COMMAND ----------

# Window that looks at each device's readings in time order
from pyspark.sql.window import Window

by_device = Window.partitionBy("device_id").orderBy("event_ts")

# For each reading, find the time of the previous reading from the same device
gaps = (
    silver.select("device_id", "event_ts")
    .withColumn("prev_ts", F.lag("event_ts").over(by_device))
    # Minutes between this reading and the previous one
    .withColumn("gap_min", (F.unix_timestamp("event_ts") - F.unix_timestamp("prev_ts")) / 60)
    # Normal gap is 5 minutes. Keep only gaps longer than 15 minutes
    .filter(F.col("gap_min") > 15)
    # The first missing reading would have been 5 minutes after the previous one
    .withColumn("gap_start", F.expr("prev_ts + INTERVAL 5 MINUTES"))
    # The gap ends when the device reports again
    .withColumn("gap_end", F.col("event_ts"))
    # How many 5-minute readings are missing
    .withColumn("missing_readings", (F.col("gap_min") / 5 - 1).cast("int"))
    # Gaps of 6 hours or more are "silent devices", shorter ones are "outages"
    .withColumn("kind", F.when(F.col("gap_min") >= 360, "silent_device").otherwise("outage"))
    .select("device_id", "gap_start", "gap_end", "gap_min", "missing_readings", "kind")
)

# Save as a Gold table
gaps.write.mode("overwrite").saveAsTable("workspace.neches.gold_gaps")

# Show how many gaps of each kind we found
display(spark.table("workspace.neches.gold_gaps").groupBy("kind").count())

# COMMAND ----------

# Read the outage answer key and look at its columns and first rows
key_out = spark.read.option("header", True).csv(f"{BUCKET}/ground_truth/outage_events.csv")
print("Columns:", key_out.columns)
print("Planted outage events:", key_out.count())
display(key_out.limit(8))

# COMMAND ----------

# Load the device list (it tells us which devices sit on which OLT and port)
devices = (
    spark.read.option("header", True)
    .csv(f"{BUCKET}/reference/devices.csv")
    .select("device_id", "olt_id", "pon_port")
)

# Convert the answer key's start and end text into real timestamps
key_ts = (
    key_out
    .withColumn("start_ts", F.to_timestamp("start"))
    .withColumn("end_ts", F.to_timestamp("end"))
)

# Device-scope events: one device each
device_events = (
    key_ts.filter(F.col("scope") == "device")
    .select("event_id", "device_id", "start_ts", "end_ts")
)

# Port-scope events: spread each event to every device on that OLT and port
port_events = (
    key_ts.filter(F.col("scope") == "port")
    .drop("device_id")
    .join(devices, ["olt_id", "pon_port"])
    .select("event_id", "device_id", "start_ts", "end_ts")
)

# One row per (event, device) that should show a gap
expected = device_events.unionByName(port_events)

# The outage gaps our pipeline found (not the silent devices)
found_gaps = spark.table("workspace.neches.gold_gaps").filter(F.col("kind") == "outage")

# Two gaps "match" if they are on the same device and their time ranges overlap
e = expected.alias("e")
g = found_gaps.alias("g")
overlap = (
    (F.col("e.device_id") == F.col("g.device_id"))
    & (F.col("g.gap_start") <= F.col("e.end_ts"))
    & (F.col("g.gap_end") >= F.col("e.start_ts"))
)

# How many expected (event, device) pairs were found by at least one gap
found_n = (
    e.join(g, overlap, "inner").select("e.event_id", "e.device_id").distinct().count()
)

# How many pipeline gaps are NOT explained by any planted event (false alarms)
false_n = g.join(e, overlap, "left_anti").count()

print("Expected (event, device) pairs:", expected.count())
print("Found by the pipeline:", found_n)
print("Missed:", expected.count() - found_n)
print("Gaps not explained by the answer key:", false_n)

# Silent devices: compare to the planted_defects answer key
silent_key = (
    spark.read.option("header", True)
    .csv(f"{BUCKET}/ground_truth/planted_defects.csv")
    .filter(F.col("defect_type") == "silent_device")
    .select("device_id")
)
silent_found = (
    spark.table("workspace.neches.gold_gaps")
    .filter(F.col("kind") == "silent_device")
    .select("device_id")
    .distinct()
)
print("Silent devices planted:", silent_key.count())
print("Silent devices found correctly:", silent_found.join(silent_key, "device_id").count())

# COMMAND ----------

# How many events of each scope are in the answer key
display(key_out.groupBy("scope").count())

# The events that are not single-device events
display(key_out.filter(F.col("scope") != "device"))

# A few rows of the device list, to compare the olt_id and pon_port formats
display(devices.limit(5))

# COMMAND ----------

# Port-wide events are labeled "pon_port" in the answer key
# Spread each one to every device on that OLT and port
port_events = (
    key_ts.filter(F.col("scope") == "pon_port")
    .drop("device_id")
    .join(devices, ["olt_id", "pon_port"])
    .select("event_id", "device_id", "start_ts", "end_ts")
)

# One row per (event, device) that should show a gap
expected = device_events.unionByName(port_events)

# Same overlap rule as before: same device and overlapping time ranges
e = expected.alias("e")
g = found_gaps.alias("g")
overlap = (
    (F.col("e.device_id") == F.col("g.device_id"))
    & (F.col("g.gap_start") <= F.col("e.end_ts"))
    & (F.col("g.gap_end") >= F.col("e.start_ts"))
)

# Expected pairs that at least one gap matches
found_n = (
    e.join(g, overlap, "inner").select("e.event_id", "e.device_id").distinct().count()
)

# Gaps that no planted event explains (false alarms)
false_n = g.join(e, overlap, "left_anti").count()

print("Expected (event, device) pairs:", expected.count())
print("Found by the pipeline:", found_n)
print("Missed:", expected.count() - found_n)
print("Gaps not explained by the answer key:", false_n)

# COMMAND ----------
