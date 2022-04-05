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

import boto3
import os
import time
import json

def s3_bucket_keys(s3_client, bucket_name, bucket_prefix):
    """Generator for listing S3 bucket keys matching prefix"""

    kwargs = {'Bucket': bucket_name, 'Prefix': bucket_prefix}
    while True:
        resp = s3_client.list_objects_v2(**kwargs)
        for obj in resp['Contents']:
            yield obj['Key']

        try:
            kwargs['ContinuationToken'] = resp['NextContinuationToken']
        except KeyError:
            break

def main(config):
    source_bucket = config["source_bucket"]
    source_prefix = config["source_prefix"]
    dest_bucket = config["dest_bucket"]
    dest_prefix = config["dest_prefix"]
    job_queue = config["job_queue"]
    job_definition = config["job_definition"]
    s3_python_script = config["s3_python_script"]
    s3_json_config = config["s3_json_config"]

    s3_client = boto3.client('s3')
    batch_client = boto3.client('batch')
   
    # get a list of objects in the source bucket
    jobs={}
    aws_region = os.environ['AWS_DEFAULT_REGION']

    for key in s3_bucket_keys(s3_client, source_bucket, source_prefix):
        if key.find(".tar") == -1:
            s3_client.copy_object(Bucket=dest_bucket, Key=f'{dest_prefix}/{key}',
                CopySource = {'Bucket': source_bucket, 'Key': key})
        else:
            job_name = str(time.time()).replace('.','-')
            response = batch_client.submit_job(
                jobName=f'extract-tar-{job_name}',
                jobQueue=job_queue,
                jobDefinition=job_definition,
                retryStrategy={'attempts': 5},
                timeout={'attemptDurationSeconds': 86400},
                containerOverrides={
                    'command': ['--key', f'{key}'],
                    'environment': [
                        {
                            'name': 'S3_PYTHON_SCRIPT',
                            'value': s3_python_script
                        },
                        {
                            'name': 'S3_JSON_CONFIG',
                            'value': s3_json_config
                        },
                        {
                            'name': 'AWS_DEFAULT_REGION',
                            'value': aws_region
                        }
                    ]
                })
            jobId = response["jobId"]
            jobs[jobId] = f"s3://{source_bucket}/{key}"

    succeeded=[]
    failed = []
    pending=[ job_id for job_id in jobs.keys() ]

    while pending:
        response = batch_client.describe_jobs(jobs=pending)
        pending = []

        for _job in response["jobs"]:
            if _job["status"] == 'SUCCEEDED':
                succeeded.append(_job["jobId"])
            elif _job["status"] == 'FAILED':
                failed.append(_job["jobId"])
            else:
                pending.append(_job["jobId"])
        
        for j in succeeded:
            print(f"Job Succeeded: {job_queue}:{j}: {jobs[j]}")
    
        for j in failed:
            print(f"Job Failed: {job_queue}:{j}: {jobs[j]}")

        for j in pending:
            print(f"Job Pending: {job_queue}:{j}: {jobs[j]}")

        time.sleep(60)
    
    if failed:
        import sys
        sys.exit(f"Failed: batch jobs: {failed}")
    
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract and load data to S3')
    parser.add_argument('--config', type=str,  help='configuration JSON file', required=True)
    
    args = parser.parse_args()

    with open(args.config) as json_file:
        config = json.load(json_file)

    main(config)