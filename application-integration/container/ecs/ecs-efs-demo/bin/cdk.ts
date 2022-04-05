#!/usr/bin/env node
import * as cdk from '@aws-cdk/core';
import { AmazonEfsIntegrationsStack } from '../lib/amazon-efs-integrations-stack';

const app = new cdk.App();

/* tslint:disable-next-line:no-unused-expression */
new AmazonEfsIntegrationsStack(app, 'AmazonEfsIntegrationsStack', {
  createEcsOnEc2Service: true,
  createEcsOnFargateService: true,
  createEfsFilesystem: false,
  createEfsAccessPoints: false,
});
