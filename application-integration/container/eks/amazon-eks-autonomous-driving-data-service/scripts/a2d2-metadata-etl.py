'''
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''

import sys

from pyspark import SparkContext
from pyspark.sql import SparkSession

from pyspark.sql.types import StructField, StructType, StringType, LongType
from pyspark.sql.functions import udf, lit

from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext

args = getResolvedOptions(sys.argv, ['s3_bucket', 's3_output_prefix'])

# set your bucket name below
s3_bucket= args['s3_bucket']
s3_output_prefix = args['s3_output_prefix']
s3_prefix = "a2d2/camera_lidar/*/camera/*/*.json" 
print(f"s3_bucket: {s3_bucket}")

# Create a schema for the dataframe
schema = StructType([
    StructField('cam_name', StringType(), True),
    StructField('cam_tstamp', LongType(), True),
    StructField('image_png', StringType(), True),
    StructField('pcld_npz', StringType(), True)
])

# create spark session
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

# read json data from S3
s3_uri = f"s3a://{s3_bucket}/{s3_prefix}"
df=spark.read.json(s3_uri, schema, multiLine=True)

df.printSchema()
df.show(10)

# drop all rows with any null value
df_clean=df.dropna(how='any')

def scene_id(file_name):
    parts=file_name.split('_')
    return parts[0]

scene_id_udf = udf(scene_id, StringType())

def s3_key(file_name, cam_name):
    parts=file_name.split('_')
    s3_key = f"a2d2/camera_lidar/{parts[0][0:8]}_{parts[0][8:]}/{parts[1]}/cam_{cam_name}/{file_name}"
    return s3_key

s3_key_udf = udf(s3_key, StringType())

def sensor_id(file_name, cam_name):
    parts=file_name.split('_')
    sensor_id = f"{parts[1]}/{cam_name}"
    return sensor_id

sensor_id_udf = udf(sensor_id, StringType())


df_image = df_clean.select(lit("a2d2").alias("vehicle_id"), 
                      scene_id_udf(df_clean.image_png).alias('scene_id'), 
                      sensor_id_udf(df_clean.image_png, df_clean.cam_name).alias('sensor_id'),
                      df.cam_tstamp.alias('data_ts'),
                      lit(s3_bucket).alias('s3_bucket'),
                      s3_key_udf(df_clean.image_png, df_clean.cam_name).alias('s3_key'))

#save prepared data frame S3 bucket
df_image.write.save(f"s3://{s3_bucket}/{s3_output_prefix}/image", format='csv', header=True)

df_pcld = df_clean.select(lit("a2d2").alias("vehicle_id"), 
                      scene_id_udf(df_clean.pcld_npz).alias('scene_id'), 
                      sensor_id_udf(df_clean.pcld_npz, df_clean.cam_name).alias('sensor_id'),
                      df.cam_tstamp.alias('data_ts'),
                      lit(s3_bucket).alias('s3_bucket'),
                      s3_key_udf(df_clean.pcld_npz, df_clean.cam_name).alias('s3_key'))

df_pcld.write.save(f"s3://{s3_bucket}/{s3_output_prefix}/pcld", format='csv', header=True)