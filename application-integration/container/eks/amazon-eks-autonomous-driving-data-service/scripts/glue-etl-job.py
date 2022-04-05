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

def s3_delete_prefix(s3_client, bucket_name, bucket_prefix):
    try:
        for key in s3_bucket_keys(s3_client, bucket_name, bucket_prefix):
            s3_client.delete_object(Bucket=bucket_name,Key=key)
    except KeyError:
        pass


def main(config):

    s3_client = boto3.client(service_name='s3')

    # delete existing output prefix in case we there is a retry attempt
    s3_delete_prefix(s3_client, config["s3_bucket"], config["s3_output_prefix"] )
   
    glue = boto3.client(service_name='glue')

    job_name=f"a2d2-metadata-etl-{str(time.time()).replace('.','')}"

    job = glue.create_job(Name=job_name, Role=config["glue_role"],
            GlueVersion='2.0',
            WorkerType='G.2X',
            NumberOfWorkers=11,
            Command={'Name': 'glueetl',
                    'ScriptLocation': config['script_location'],
                    'PythonVersion': '3'
                    }, 
            DefaultArguments = {'--job-language': 'python',
                                '--s3_bucket':   config["s3_bucket"],
                                '--s3_output_prefix': config["s3_output_prefix"]})

    job_run = glue.start_job_run(JobName=job['Name'])
    status = glue.get_job_run(JobName=job['Name'], RunId=job_run['JobRunId'])
    print(str(status))

    run_state = status['JobRun']['JobRunState']
    while run_state == "RUNNING" or run_state == "STARTING" or run_state == "STOPPING" or run_state == "STOPPED":
        print(f"Glue Job is {run_state}")
        time.sleep(30)
        status = glue.get_job_run(JobName=job['Name'], RunId=job_run['JobRunId'])
        run_state = status['JobRun']['JobRunState']
    
    if run_state != "SUCCEEDED":
        import sys
        sys.exit(f"Glue job final status: {run_state}")

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Glue ETL Job')
    parser.add_argument('--config', type=str,  help='Glue ETL Configuration file', required=True)
    
    args = parser.parse_args()

    with open(args.config) as json_file:
        config = json.load(json_file)

    main(config)

