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


def main(config):
    definition = config["definition"]
    role_arn = config["role_arn"]
    
    sfn_client = boto3.client('stepfunctions')
    response = sfn_client.create_state_machine(
        name=f"state-machine-{str(time.time()).replace('.','-')}",
        definition=json.dumps(definition),
        roleArn=role_arn,
        type='STANDARD'
    )
    print(response)

    response = sfn_client.start_execution(
        stateMachineArn=response['stateMachineArn'],
        name=f"state-machine-execution-{str(time.time()).replace('.','-')}"
    )
    print(response)
    
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='batch job for extract and load to S3')
    parser.add_argument('--config', type=str,  help='configuration JSON file', required=True)
    
    args = parser.parse_args()

    with open(args.config) as json_file:
        config = json.load(json_file)

    main(config)