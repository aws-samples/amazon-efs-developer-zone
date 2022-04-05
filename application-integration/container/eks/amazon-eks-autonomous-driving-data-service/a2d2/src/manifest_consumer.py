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
from multiprocessing import Process
import logging
import json

from kafka import KafkaConsumer, KafkaAdminClient
from util import random_string, is_close_msg

class ManifestConsumer(Process):
    def __init__(self, servers=None, response_topic=None):
        Process.__init__(self)
        self.logger = logging.getLogger("manifest_consumer")
        logging.basicConfig(
            format='%(asctime)s.%(msecs)s:%(name)s:%(thread)d:%(levelname)s:%(process)d:%(message)s',
            level=logging.INFO)

        self.servers = servers
        self.response_topic = response_topic
        
        
    def run(self):
        try:
            consumer = KafkaConsumer(self.response_topic, 
                                bootstrap_servers=self.servers,
                                auto_offset_reset="earliest",
                                client_id=random_string())

            self.logger.info("manifest consumer on {0} kafka topic".format(self.response_topic))

            for message in consumer:
                try:
                    json_str = message.value
                    json_msg = json.loads(json_str)
                    if is_close_msg(json_msg):
                        print(json_str)
                        break
                except Exception as e:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
                    self.logger.error(str(exc_type))
                    self.logger.error(str(exc_value))
                    break

            consumer.close()
            admin = KafkaAdminClient(bootstrap_servers=self.servers)
            admin.delete_topics([self.response_topic])
            admin.close()
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))
