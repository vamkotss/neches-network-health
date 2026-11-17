# Databricks notebook source
# Import Spark's helper functions (F)
from pyspark.sql import functions as F

# The S3 bucket that holds all project files
BUCKET = "s3://neches-network-health-vamsi-2711"

# Where new telemetry files arrive
LANDING = f"{BUCKET}/landing/telemetry/"

# Auto Loader's memory of which files it already loaded
CHECKPOINT = f"{BUCKET}/_checkpoints/bronze_telemetry"

# Where Auto Loader keeps the column layout it figured out
SCHEMA_DIR = f"{BUCKET}/_schemas/bronze_telemetry"

# The Bronze table to fill
TARGET = "workspace.neches.bronze_telemetry"

# Make sure the schema (table folder) exists
spark.sql("CREATE SCHEMA IF NOT EXISTS workspace.neches")

# Read any new files with Auto Loader and tag each row with its source file and load time
stream = (
    spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", SCHEMA_DIR)
    .option("cloudFiles.inferColumnTypes", "true")
    .load(LANDING)
    .withColumn("_source_file", F.col("_metadata.file_path"))
    .withColumn("_ingested_at", F.current_timestamp())
)

# Write new rows into Bronze; availableNow means "process what is waiting, then stop"
query = (
    stream.writeStream.option("checkpointLocation", CHECKPOINT)
    .option("mergeSchema", "true")
    .trigger(availableNow=True)
    .toTable(TARGET)
)
query.awaitTermination()

# Print the row count so the job log shows what happened
print("Bronze rows:", spark.table(TARGET).count())

# COMMAND ----------
