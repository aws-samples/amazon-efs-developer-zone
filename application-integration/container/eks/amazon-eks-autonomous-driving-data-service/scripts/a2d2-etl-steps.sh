#!/bin/bash
#Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# 
#Permission is hereby granted, free of charge, to any person obtaining a copy of this
#software and associated documentation files (the "Software"), to deal in the Software
#without restriction, including without limitation the rights to use, copy, modify,
#merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
#permit persons to whom the Software is furnished to do so.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
#PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
#OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# set s3 bucket name
scripts_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DIR=$scripts_dir/..

[[ -z "${s3_bucket_name}" ]] && echo "s3_bucket_name variable required" && exit 1
[[ -z "${batch_job_queue}" ]] && echo "batch_job_queue variable required" && exit 1
[[ -z "${batch_job_definition}" ]] && echo "batch_job_definition variable required" && exit 1
[[ -z "${stepfunctions_role_arn}" ]] && echo "stepfunctions_role_arn variable required" && exit 1
[[ -z "${glue_job_role_arn}" ]] && echo "glue_job_role_arn variable required" && exit 1
[[ -z "${redshift_cluster_role_arn}" ]] && echo "redshift_cluster_role_arn variable required" && exit 1
[[ -z "${redshift_cluster_host}" ]] && echo "redshift_cluster_host variable required" && exit 1
[[ -z "${redshift_cluster_port}" ]] && echo "redshift_cluster_port variable required" && exit 1
[[ -z "${redshift_cluster_username}" ]] && echo "redshift_cluster_username variable required" && exit 1
[[ -z "${redshift_cluster_dbname}" ]] && echo "redshift_cluster_dbname variable required" && exit 1
[[ -z "${redshift_cluster_password}" ]] && echo "redshift_cluster_password variable required" && exit 1

$scripts_dir/pythonfroms3-focal-ecr-image.sh

# create requirements.txt
cat >$scripts_dir/requirements.txt <<EOL
psycopg2-binary
pandas
numpy
EOL

aws s3 cp $scripts_dir/a2d2-metadata-etl.py s3://$s3_bucket_name/scripts/a2d2-metadata-etl.py
aws s3 cp $scripts_dir/s3-extract-tar.py s3://$s3_bucket_name/scripts/s3-extract-tar.py
aws s3 cp $scripts_dir/s3-extract-load.py s3://$s3_bucket_name/scripts/s3-extract-load.py
aws s3 cp $scripts_dir/glue-etl-job.py s3://$s3_bucket_name/scripts/glue-etl-job.py
aws s3 cp $scripts_dir/extract-bus-data.py s3://$s3_bucket_name/scripts/extract-bus-data.py
aws s3 cp $scripts_dir/setup-redshift-db.py s3://$s3_bucket_name/scripts/setup-redshift-db.py
aws s3 cp $scripts_dir/requirements.txt s3://$s3_bucket_name/scripts/requirements.txt

tmp_dir="/efs/tmp-$(date +%s)"

# Create glue.config 
s3_glue_output_prefix="glue/a2d2/$(date +%s)"

cat >$DIR/a2d2/config/glue.config <<EOL
{
  "s3_bucket": "${s3_bucket_name}",
  "s3_output_prefix": "${s3_glue_output_prefix}",
  "glue_role": "${glue_job_role_arn}",
  "script_location": "s3://${s3_bucket_name}/scripts/a2d2-metadata-etl.py"
}
EOL
chown ubuntu:ubuntu $DIR/a2d2/config/glue.config

s3_bus_output_prefix="bus_data/a2d2/$(date +%s)"

cat >$DIR/a2d2/config/bus_data.config <<EOL
{
  "s3_bucket": "${s3_bucket_name}",
  "s3_input_prefix": "a2d2/camera_lidar",
  "s3_input_suffix": "_bus_signals.json",
  "s3_output_prefix": "${s3_bus_output_prefix}",
  "vehicle_id": "a2d2",
  "tmp_dir": "${tmp_dir}",
  "script_location": "s3://${s3_bucket_name}/scripts/extract-bus-data.py"
}
EOL
chown ubuntu:ubuntu $DIR/a2d2/config/bus_data.config

aws s3 cp $DIR/a2d2/data/sensors.csv s3://${s3_bucket_name}/redshift/sensors.csv
aws s3 cp $DIR/a2d2/data/vehicle.csv s3://${s3_bucket_name}/redshift/vehicle.csv
            
# Create redshift.configs
cat >$DIR/a2d2/config/redshift.config <<EOL
{
  "host": "${redshift_cluster_host}",
  "port": "${redshift_cluster_port}",
  "user": "${redshift_cluster_username}",
  "dbname": "${redshift_cluster_dbname}",
  "password": "${redshift_cluster_password}",
  "queries": [
    "CREATE SCHEMA IF NOT EXISTS a2d2",
    "CREATE TABLE IF NOT EXISTS a2d2.sensor ( sensorid VARCHAR(255) NOT NULL ENCODE lzo ,description VARCHAR(255) ENCODE lzo ,PRIMARY KEY (sensorid)) DISTSTYLE ALL",
    "CREATE TABLE IF NOT EXISTS a2d2.vehicle ( vehicleid VARCHAR(255) NOT NULL ENCODE lzo ,description VARCHAR(255) ENCODE lzo ,PRIMARY KEY (vehicleid)) DISTSTYLE ALL",
    "CREATE TABLE IF NOT EXISTS a2d2.drive_data ( vehicle_id varchar(255) encode Text255 not NULL, scene_id varchar(255) encode Text255 not NULL, sensor_id varchar(255) encode Text255 not NULL, data_ts BIGINT not NULL sortkey, s3_bucket VARCHAR(255) encode lzo NOT NULL, s3_key varchar(255) encode lzo NOT NULL, primary key(vehicle_id, scene_id), FOREIGN KEY(vehicle_id) references a2d2.vehicle(vehicleid), FOREIGN KEY(sensor_id) references a2d2.sensor(sensorid)) DISTSTYLE AUTO",
    "CREATE TABLE IF NOT EXISTS a2d2.bus_data ( vehicle_id varchar(255) encode Text255 not NULL, scene_id varchar(255) encode Text255 not NULL, data_ts BIGINT not NULL sortkey, acceleration_x FLOAT4 not NULL, acceleration_y FLOAT4 not NULL, acceleration_z FLOAT4 not NULL, accelerator_pedal FLOAT4 not NULL, accelerator_pedal_gradient_sign SMALLINT not NULL, angular_velocity_omega_x FLOAT4 not NULL, angular_velocity_omega_y FLOAT4 not NULL, angular_velocity_omega_z FLOAT4 not NULL, brake_pressure FLOAT4 not NULL, distance_pulse_front_left FLOAT4 not NULL, distance_pulse_front_right FLOAT4 not NULL, distance_pulse_rear_left FLOAT4 not NULL, distance_pulse_rear_right FLOAT4 not NULL, latitude_degree FLOAT4 not NULL, latitude_direction SMALLINT not NULL, longitude_degree FLOAT4 not NULL, longitude_direction SMALLINT not NULL, pitch_angle FLOAT4 not NULL, roll_angle FLOAT4 not NULL, steering_angle_calculated FLOAT4 not NULL, steering_angle_calculated_sign SMALLINT not NULL, vehicle_speed FLOAT4 not NULL, primary key(vehicle_id, scene_id), FOREIGN KEY(vehicle_id) references a2d2.vehicle(vehicleid) ) DISTSTYLE AUTO",
    "COPY a2d2.sensor FROM 's3://${s3_bucket_name}/redshift/sensors.csv' iam_role  '${redshift_cluster_role_arn}' CSV",
    "COPY a2d2.vehicle FROM 's3://${s3_bucket_name}/redshift/vehicle.csv' iam_role  '${redshift_cluster_role_arn}' CSV",
    "COPY a2d2.drive_data FROM 's3://${s3_bucket_name}/${s3_glue_output_prefix}/image/' iam_role  '${redshift_cluster_role_arn}' CSV IGNOREHEADER 1",
    "COPY a2d2.drive_data FROM 's3://${s3_bucket_name}/${s3_glue_output_prefix}/pcld/' iam_role  '${redshift_cluster_role_arn}' CSV IGNOREHEADER 1",
    "COPY a2d2.bus_data FROM 's3://${s3_bucket_name}/${s3_bus_output_prefix}/' iam_role  '${redshift_cluster_role_arn}' CSV IGNOREHEADER 1"
  ]
}
EOL
chown ubuntu:ubuntu $DIR/a2d2/config/redshift.config

# Create a2d2-data.config 
cat >$DIR/a2d2/config/a2d2-data.config <<EOL
{
  "source_bucket": "aev-autonomous-driving-dataset",
  "source_prefix": "",
  "dest_bucket": "${s3_bucket_name}",
  "dest_prefix": "a2d2",
  "job_definition": "${batch_job_definition}",
  "job_queue": "${batch_job_queue}",
  "s3_python_script": "s3://${s3_bucket_name}/scripts/s3-extract-tar.py",
  "s3_json_config": "s3://${s3_bucket_name}/config/a2d2-data.config",
  "tmp_dir": "${tmp_dir}"
}
EOL

aws s3 cp $DIR/a2d2/config/a2d2-data.config s3://$s3_bucket_name/config/a2d2-data.config
aws s3 cp $DIR/a2d2/config/glue.config s3://$s3_bucket_name/config/glue.config
aws s3 cp $DIR/a2d2/config/bus_data.config s3://$s3_bucket_name/config/bus_data.config
aws s3 cp $DIR/a2d2/config/redshift.config s3://$s3_bucket_name/config/redshift.config

job_name1="a2d2-extract-raw-data-$(date +%s)"
job_name2="a2d2-extract-meta-data-$(date +%s)"
job_name3="a2d2-extract-bus-data-$(date +%s)"
job_name4="a2d2-load-data-$(date +%s)"

# Create a2d2-sfn.configs 
cat >$DIR/a2d2/config/a2d2-sfn.config <<EOL
{
  "role_arn": "${stepfunctions_role_arn}",
  "definition": {
    "Comment": "Steps for a2d2 data processing workflow",
    "StartAt": "A2D2ExtractRawData",
    "States": {
      "A2D2ExtractRawData": {
        "Type": "Task",
        "Resource": "arn:aws:states:::batch:submitJob.sync",
        "Parameters": {
          "JobQueue": "${batch_job_queue}",
          "JobDefinition": "${batch_job_definition}",
          "JobName": "${job_name1}",
          "ContainerOverrides": {
            "Environment": [
              {
                "Name": "S3_PYTHON_SCRIPT",
                "Value": "s3://${s3_bucket_name}/scripts/s3-extract-load.py"
              },
              {
                "Name": "S3_JSON_CONFIG",
                "Value": "s3://${s3_bucket_name}/config/a2d2-data.config"
              }
            ] 
          },
          "RetryStrategy": {"Attempts": 5},
          "Timeout": {"AttemptDurationSeconds": 172800}
        },
        "Next": "A2D2ExtractMetaData"
      },
      "A2D2ExtractMetaData": {
        "Type": "Task",
        "Resource": "arn:aws:states:::batch:submitJob.sync",
        "Parameters": {
          "JobQueue": "${batch_job_queue}",
          "JobDefinition": "${batch_job_definition}",
          "JobName": "${job_name2}",
          "ContainerOverrides": {
            "Environment": [
              {
                "Name": "S3_PYTHON_SCRIPT",
                "Value": "s3://${s3_bucket_name}/scripts/glue-etl-job.py"
              },
              {
                "Name": "S3_JSON_CONFIG",
                "Value": "s3://${s3_bucket_name}/config/glue.config"
              }
            ] 
          },
          "RetryStrategy": {"Attempts": 2},
          "Timeout": {"AttemptDurationSeconds": 3600}
        },
        "Next": "A2D2ExtractBusData"
      },
      "A2D2ExtractBusData": {
        "Type": "Task",
        "Resource": "arn:aws:states:::batch:submitJob.sync",
        "Parameters": {
          "JobQueue": "${batch_job_queue}",
          "JobDefinition": "${batch_job_definition}",
          "JobName": "${job_name3}",
          "ContainerOverrides": {
            "Environment": [
              {
                "Name": "S3_PYTHON_SCRIPT",
                "Value": "s3://${s3_bucket_name}/scripts/extract-bus-data.py"
              },
              {
                "Name": "S3_JSON_CONFIG",
                "Value": "s3://${s3_bucket_name}/config/bus_data.config"
              },
              {
                "Name": "S3_REQUIREMENTS_TXT",
                "Value": "s3://$s3_bucket_name/scripts/requirements.txt"
              }
            ] 
          },
          "RetryStrategy": {"Attempts": 2},
          "Timeout": {"AttemptDurationSeconds": 3600}
        },
        "Next": "A2D2UploadMetaData"
      },
      "A2D2UploadMetaData": {
        "Type": "Task",
        "Resource": "arn:aws:states:::batch:submitJob.sync",
        "Parameters": {
          "JobQueue": "${batch_job_queue}",
          "JobDefinition": "${batch_job_definition}",
          "JobName": "${job_name4}",
          "ContainerOverrides": {
            "Environment": [
              {
                "Name": "S3_PYTHON_SCRIPT",
                "Value": "s3://$s3_bucket_name/scripts/setup-redshift-db.py"
              },
              {
                "Name": "S3_JSON_CONFIG",
                "Value": "s3://$s3_bucket_name/config/redshift.config"
              },
              {
                "Name": "S3_REQUIREMENTS_TXT",
                "Value": "s3://$s3_bucket_name/scripts/requirements.txt"
              }
            ] 
          },
          "RetryStrategy": {"Attempts": 2},
          "Timeout": {"AttemptDurationSeconds": 1800}
        },
        "End": true
      }
    }
  }
}
EOL

python3 $scripts_dir/step-functions.py --config $DIR/a2d2/config/a2d2-sfn.config