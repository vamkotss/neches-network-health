# Databricks notebook source
# Lists the folders inside the landing area of your S3 bucket
display(dbutils.fs.ls("s3://neches-network-health-vamsi-2711/landing/telemetry/"))

# COMMAND ----------

# Import Spark's built-in helper functions (we call them F.something)
from pyspark.sql import functions as F

# The bucket that holds all of the project's files
BUCKET = "s3://neches-network-health-vamsi-2711"

# Where Auto Loader looks for new telemetry files
LANDING = f"{BUCKET}/landing/telemetry/"

# Auto Loader's memory of which files it already loaded (so nothing loads twice)
CHECKPOINT = f"{BUCKET}/_checkpoints/bronze_telemetry"

# Where Auto Loader stores the column layout it figured out
SCHEMA_DIR = f"{BUCKET}/_schemas/bronze_telemetry"

# The table we are creating: catalog "workspace", schema "neches", table "bronze_telemetry"
TARGET = "workspace.neches.bronze_telemetry"

# Make the "neches" schema (a folder for our tables) if it does not exist yet
spark.sql("CREATE SCHEMA IF NOT EXISTS workspace.neches")

# Start reading the landing files with Auto Loader ("cloudFiles")
stream = (
    spark.readStream.format("cloudFiles")
    # Our files are JSON lines (gzip-compressed, which Spark unzips automatically)
    .option("cloudFiles.format", "json")
    # Remember the column layout here
    .option("cloudFiles.schemaLocation", SCHEMA_DIR)
    # Guess real types (numbers, etc.) instead of treating everything as text
    .option("cloudFiles.inferColumnTypes", "true")
    # Read from the landing folder
    .load(LANDING)
    # Add a column saying which file each row came from
    .withColumn("_source_file", F.col("_metadata.file_path"))
    # Add a column saying when we loaded the row
    .withColumn("_ingested_at", F.current_timestamp())
)

# Write what we read into the Bronze table
query = (
    stream.writeStream
    # Save progress here so a re-run only loads new files
    .option("checkpointLocation", CHECKPOINT)
    # Allow new columns to appear later without breaking the pipeline
    .option("mergeSchema", "true")
    # Process everything available now, then stop (instead of running forever)
    .trigger(availableNow=True)
    # Create or append to the table
    .toTable(TARGET)
)

# Wait until all files are loaded
query.awaitTermination()

# COMMAND ----------

# Count the rows in the Bronze table. We expect 2,042,784, the number the generator reported.
print(spark.table("workspace.neches.bronze_telemetry").count())

# COMMAND ----------

# Show 5 sample rows so you can see what raw data looks like
display(spark.table("workspace.neches.bronze_telemetry").limit(5))

# COMMAND ----------
