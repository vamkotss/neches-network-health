# Databricks notebook source
# Import Spark's helper functions (F) and the window tool for looking at neighbouring rows
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Use UTC for all times
spark.conf.set("spark.sql.session.timeZone", "UTC")

# Load the cleaned Silver table
silver = spark.table("workspace.neches.silver_telemetry")

# The moment the data starts, used to count "days since start"
DATA_START = "2026-11-01 00:00:00"

# ---------- Gold table 1: which devices are slowly failing? ----------

# Turn each reading's time into "days since the data started"
with_days = silver.withColumn(
    "day_num",
    (F.unix_timestamp("event_ts") - F.unix_timestamp(F.lit(DATA_START))) / 86400,
)

# For each device, fit a straight line through its receive power over time
# regr_slope = dB change per day (negative means the signal is getting weaker)
trend = with_days.groupBy("device_id").agg(
    F.regr_slope("rx_power_dbm", "day_num").alias("rx_slope_db_per_day"),
    F.avg("rx_power_dbm").alias("rx_avg_dbm"),
    F.min("rx_power_dbm").alias("rx_min_dbm"),
    F.count("*").alias("readings"),
)

# Flag a device as degrading when its signal drops by more than 0.05 dB per day
flagged = trend.withColumn("is_degrading", F.col("rx_slope_db_per_day") <= -0.05)
flagged.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    "workspace.neches.gold_device_trend"
)

# ---------- Gold table 2: outages and silent devices (gaps in reporting) ----------

# Look at each device's readings in time order
by_device = Window.partitionBy("device_id").orderBy("event_ts")

gaps = (
    silver.select("device_id", "event_ts")
    # Time of the previous reading from the same device
    .withColumn("prev_ts", F.lag("event_ts").over(by_device))
    # Minutes between the two readings (normally 5)
    .withColumn("gap_min", (F.unix_timestamp("event_ts") - F.unix_timestamp("prev_ts")) / 60)
    # Keep only gaps longer than 15 minutes
    .filter(F.col("gap_min") > 15)
    # The first missing reading would have been 5 minutes after the previous one
    .withColumn("gap_start", F.expr("prev_ts + INTERVAL 5 MINUTES"))
    # The gap ends when the device reports again
    .withColumn("gap_end", F.col("event_ts"))
    # How many 5-minute readings are missing
    .withColumn("missing_readings", (F.col("gap_min") / 5 - 1).cast("int"))
    # 6 hours or more = silent device; shorter = outage
    .withColumn("kind", F.when(F.col("gap_min") >= 360, "silent_device").otherwise("outage"))
    .select("device_id", "gap_start", "gap_end", "gap_min", "missing_readings", "kind")
)
gaps.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    "workspace.neches.gold_gaps"
)

# ---------- Gold table 3: late-arriving data, per day ----------

late_daily = (
    # A reading is late when it arrived after the hour it happened in (positive delay)
    silver.filter(F.col("arrival_delay_min") > 0)
    .withColumn("event_date", F.to_date("event_ts"))
    .groupBy("event_date")
    .agg(
        F.count("*").alias("late_rows"),
        F.round(F.avg("arrival_delay_min"), 1).alias("avg_delay_min"),
        F.max("arrival_delay_min").alias("max_delay_min"),
    )
)
late_daily.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    "workspace.neches.gold_late_arrivals_daily"
)

# ---------- Print a summary so the job log shows what happened ----------
print("Degrading devices:", spark.table("workspace.neches.gold_device_trend").filter("is_degrading").count())
print("Outage gaps:", spark.table("workspace.neches.gold_gaps").filter("kind = 'outage'").count())
print("Silent devices:", spark.table("workspace.neches.gold_gaps").filter("kind = 'silent_device'").count())
print("Late rows:", spark.table("workspace.neches.gold_late_arrivals_daily").agg(F.sum("late_rows")).first()[0])

# COMMAND ----------
