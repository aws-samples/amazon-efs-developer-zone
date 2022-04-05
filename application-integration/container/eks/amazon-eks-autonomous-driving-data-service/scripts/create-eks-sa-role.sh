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

scripts_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

CLUSTER_NAME=
BUCKET_NAME=
if [ "$#" -eq 2 ]; then
    CLUSTER_NAME=$1
    BUCKET_NAME=$2
else
    echo "usage: $0 <cluster-name> <bucket-name>"
    exit 1
fi

DATE=$(date +%s%N)
ISSUER_URL=$(aws eks describe-cluster \
                       --name $CLUSTER_NAME \
                       --query cluster.identity.oidc.issuer \
                       --output text)

# STEP 1: create IAM role and attach the target policy:
ISSUER_HOSTPATH=$(echo $ISSUER_URL | cut -f 3- -d'/')
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PROVIDER_ARN="arn:aws:iam::$ACCOUNT_ID:oidc-provider/$ISSUER_HOSTPATH"

ROLE_NAME="eks-sa-mozart-${DATE}-role"
cat > /tmp/$ROLE_NAME-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "$PROVIDER_ARN"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "${ISSUER_HOSTPATH}:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
EOF

POLICY_NAME=${ROLE_NAME}-policy
cat > /tmp/${POLICY_NAME}.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:List*",
                "s3:Get*",
                "s3:PutObject*",
                "s3:DeleteObject*"
            ],
            "Resource": [
                "arn:aws:s3:::$BUCKET_NAME",
                "arn:aws:s3:::$BUCKET_NAME/*"
            ]
        }
    ]
}
EOF

aws iam create-policy \
	--policy-name ${POLICY_NAME} \
	--policy-document file:///tmp/${POLICY_NAME}.json \
	--output text


aws iam create-role \
          --role-name $ROLE_NAME \
          --assume-role-policy-document file:///tmp/$ROLE_NAME-trust-policy.json \
	  --output text

aws iam attach-role-policy --role-name ${ROLE_NAME} \
	  --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}" \
	  --output text

role_arn=$(aws iam list-roles | grep Arn | grep $ROLE_NAME | awk -F " " '{print $2}' | sed -e s"/,//g" -e s"/\"//g" )

echo "Updating EKS Pod Role Arn: $role_arn"

echo "Updating $scripts_dir/../a2d2/fsx/stage-data-a2d2.yaml"
sed -i -e "s|eks\.amazonaws\.com/role-arn:.*|eks.amazonaws.com/role-arn: ${role_arn}|g" \
	-e "s|value:[[:blank:]]\+$|value: ${BUCKET_NAME}|g"   $scripts_dir/../a2d2/fsx/stage-data-a2d2.yaml

echo "Updating $scripts_dir/../a2d2/efs/stage-data-a2d2.yaml"
sed -i -e "s|eks\.amazonaws\.com/role-arn:.*|eks.amazonaws.com/role-arn: ${role_arn}|g" \
	-e "s|value:[[:blank:]]\+$|value: ${BUCKET_NAME}|g" $scripts_dir/../a2d2/efs/stage-data-a2d2.yaml

echo "Updating $scripts_dir/../a2d2/charts/a2d2-data-service/values.yaml"
sed -i -e "s|roleArn:.*|roleArn: ${role_arn}|g" $scripts_dir/../a2d2/charts/a2d2-data-service/values.yaml
