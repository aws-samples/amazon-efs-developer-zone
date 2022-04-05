#!/usr/bin/env bash

export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity | jq .AccountId)
