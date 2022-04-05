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

import psycopg2
import boto3

import sys, traceback
import threading, logging, time
import json
import random
import string
import time

class DatabaseReader:
    def __init__(self, dbconfig=None):
        logging.basicConfig(
            format='%(asctime)s.%(msecs)s:%(name)s:%(thread)d:%(levelname)s:%(process)d:%(message)s',
            level=logging.INFO)
        self.logger = logging.getLogger("dbreader")

        self.dbconfig = dbconfig
    
    def connect(self):
        try:
            dbname = self.dbconfig["dbname"]
            host = self.dbconfig["host"]
            port = self.dbconfig["port"]
            user = self.dbconfig["user"]
            password = self.dbconfig["password"]

            secrets_client = boto3.client('secretsmanager')
            response = secrets_client.get_secret_value(SecretId=password)
            self.con=psycopg2.connect(dbname=dbname, host=host, port=port, 
                    user=user, password=response['SecretString'])
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))

    def query(self, query):
        result = None
        try:
            cur = self.con.cursor()
            cur.execute(query)
            result = cur.fetchall()
            cur.close()
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))

        return result

    def close(self):
        try:
            if self.con:
                self.con.close()
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            self.logger.error(str(exc_type))
            self.logger.error(str(exc_value))

def main(config, query):
    db = DatabaseReader(dbconfig=config["database"])
    db.connect()
    print(db.query(query))
    db.close()


import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='DatabaseReader thread')
    parser.add_argument('--config', type=str,  help='configuration file', required=True)
    parser.add_argument('--query', type=str,  help='query', required=True)
    
    args = parser.parse_args()

    with open(args.config) as json_file:
        config = json.load(json_file)

    main(config, args.query)
