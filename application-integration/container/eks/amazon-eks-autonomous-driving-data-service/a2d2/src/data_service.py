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
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys, traceback
import threading, logging, time
import json
import random
import string
import time

from kafka import KafkaConsumer
from data_response import DataResponse
from util import random_string, validate_data_request


class DataService(threading.Thread):
    def __init__(self, config):
        threading.Thread.__init__(self)
        self.config = config
        self.logger = logging.getLogger("data_service")
        logging.basicConfig(
            format='%(asctime)s.%(msecs)s:%(name)s:%(thread)d:%(levelname)s:%(process)d:%(message)s',
            level=logging.INFO)
        
    def run(self):
        try:
            topic = self.config["kafka_topic"]

            client_id = random_string()
            consumer = KafkaConsumer(topic, 
                        bootstrap_servers=self.config["servers"],
                        client_id=client_id,
                        group_id="a2d2-data-service")

            self.logger.info("running data service: {0}:{1}".format(client_id, topic))

            tasks = []
            max_tasks = int(self.config["max_response_tasks"])

            for message in consumer:
                try:
                    json_msg = json.loads(message.value) 
                    request = json_msg["request"]
                    self.logger.info("recvd request: {0}".format(request))
                    validate_data_request(request)
                    t = DataResponse(dbconfig=self.config['database'], 
                        servers=self.config["servers"], 
                        request=request, 
                        data_store=self.config['data_store'],
                        calibration=self.config['calibration'])

                    if len(tasks) < max_tasks:
                        tasks.append(t)
                    else:
                        oldest=tasks.pop(0)
                        oldest.join()
                        tasks.append(t)

                    assert(len(tasks) <= max_tasks)
                    t.start()

                except Exception as e:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
                    self.logger.error(str(e))


        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))

def main(config):
    
    tasks = [
        DataService(config),
    ]

    for t in tasks:
        t.start()

        
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Kafka data service process')
    parser.add_argument('--config', type=str,  help='configuration file', required=True)
    
    args = parser.parse_args()

    with open(args.config) as json_file:
        config = json.load(json_file)

    main(config)
