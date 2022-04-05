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
import sys, traceback
import logging
import json


def main(config):
    logger = logging.getLogger("data_service")
    logging.basicConfig(
        format='%(asctime)s.%(msecs)s:%(name)s:%(thread)d:%(levelname)s:%(process)d:%(message)s',
        level=logging.INFO)

    try:
        with open(config['cluster-properties'], mode='r') as file:
            file_content = file.read()
            client = boto3.client('kafka')

            kafka_config = client.create_configuration(
                Description=config['config-description'],
                Name=config['config-name'],
                ServerProperties=file_content
            )

            logger.info(str(kafka_config))
            cluster_info = client.describe_cluster( ClusterArn=config['cluster-arn'])

            response = client.update_cluster_configuration(
                ClusterArn=config['cluster-arn'],
                ConfigurationInfo={
                        'Arn': kafka_config['Arn'],
                        'Revision': kafka_config['LatestRevision']['Revision'] 
                },
                CurrentVersion=cluster_info['ClusterInfo']['CurrentVersion']
            )
            logger.info(str(response))

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
        logger.error(str(e))
            
    
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Setup Kafka configuration for autonomous driving data service')
    parser.add_argument('--config', type=str,  help='Kafka configuration JSON file', required=True)
    
    args = parser.parse_args()
    with open(args.config) as json_file:
        config = json.load(json_file)

    main(config)
