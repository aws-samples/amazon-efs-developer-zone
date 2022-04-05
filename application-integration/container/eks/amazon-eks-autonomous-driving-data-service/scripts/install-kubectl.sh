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

# WARNING: THIS FILE IS DEPRECATED AND IS NOT USED 

# set region
region=
cluster=

if [ "$#" -eq 2 ]; then
    region=$1
    echo "AWS region: $region"

    cluster=$2
    echo "EKS cluster name: $cluster"
else
    echo "usage: $0 <aws-region> <eks-cluster-name>"
    exit 1
fi

# Set to kubectl version for your EKS cluster
KubectlVersion="1.21.2/2021-07-05"
echo "Using kubectl version: $KubectlVersion; change kubectl version if incompatible with your EKS cluster"

sudo mkdir -p /usr/local/bin
sudo curl -o /usr/local/bin/kubectl https://amazon-eks.s3.us-west-2.amazonaws.com/$KubectlVersion/bin/linux/amd64/kubectl
sudo chmod a+x /usr/local/bin/kubectl
sudo curl -o /usr/local/bin/aws-iam-authenticator https://amazon-eks.s3.us-west-2.amazonaws.com/$KubectlVersion/bin/linux/amd64/aws-iam-authenticator

aws sts get-caller-identity
aws eks --region $region update-kubeconfig --name $cluster 
