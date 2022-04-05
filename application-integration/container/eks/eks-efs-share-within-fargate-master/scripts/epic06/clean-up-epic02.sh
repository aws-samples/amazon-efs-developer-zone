#!/bin/bash

export AWS_PAGER=""

BASEDIR=$(dirname "$0")

# Cluster Name
K8S_CLUSTER_NAME=$1
# Security Group Name
SG_EFS_NAME=$2
# File System Token
FS_TOKEN=$3
# KMS CMK Key Alias
KMS_ALIAS=$4

source $BASEDIR/../util.sh

echo "########################################################"
echo "EPIC 02 - Deleting EFS, EFS Mount, Security Group, and KMS Key"

################################################################
# Getting the VPC ID from Kubernetes cluster
VPC_ID=`aws eks describe-cluster --name $K8S_CLUSTER_NAME | jq --raw-output '.cluster.resourcesVpcConfig.vpcId'`
if [ -z "${VPC_ID// }" ]; then
    echo "VPC ID was not found for this cluster ${K8S_CLUSTER_NAME}."
    exit 99
fi
echo "Working with VPC ID: ${VPC_ID}"

################################################################
# Deleting Mount Targets

# Getting the EFS File System ID
FS_ID=`aws efs describe-file-systems \
                --creation-token ${FS_TOKEN} \
                | jq --raw-output '.FileSystems[] | .FileSystemId'`
if [ ! -z "${FS_ID// }" ]; then
    echo "Working with EFS File System ID: ${FS_ID}"

    # Getting the NAT Gateways IDs for discovering the private subnets
    NAT_GATEWAYS=`aws ec2 describe-nat-gateways \
                            --filter "Name=vpc-id,Values=${VPC_ID}" "Name=state,Values=available" \
                                | jq --raw-output '.NatGateways[] | .NatGatewayId'`
    IFS=$'\n' read -rd '' -a NAT_GATEWAYS <<<"$NAT_GATEWAYS"

    # Discovering private subnets through route table (destination 0.0.0.0/0, target natgtw )
    PRIVATE_SUBNETS=()
    for natgtw in "${NAT_GATEWAYS[@]}"
    do
        # Getting the subnets per route table
        SUBNETS_PER_NAT=`aws ec2 describe-route-tables \
                            --filter "Name=vpc-id,Values=${VPC_ID}" \
                                    "Name=route.destination-cidr-block,Values=0.0.0.0/0" \
                                    "Name=route.nat-gateway-id,Values=${natgtw}" \
                            | jq --raw-output '.RouteTables[] | .Associations[] | .SubnetId'`
        IFS=$'\n' read -rd '' -a SUBNETS_PER_NAT <<<"$SUBNETS_PER_NAT"

        PRIVATE_SUBNETS+=(${SUBNETS_PER_NAT[@]})
    done

    # Deleting the mount target per private subnet
    for pvtsubnet in "${PRIVATE_SUBNETS[@]}"
    do
        MNT_TGT_ID=`aws efs describe-mount-targets \
                            --file-system-id "${FS_ID}" \
                                | jq --raw-output --arg subnetid "${pvtsubnet}" \
                                '.MountTargets[] | select(.SubnetId==$subnetid) | .MountTargetId'`
        if [ ! -z "${MNT_TGT_ID// }" ]; then
            aws efs delete-mount-target --mount-target-id "${MNT_TGT_ID}"
        fi
    done

    ################################################################
    # Deleting EFS
    echo "Wait for deletion before deleting FS"
    MOUNT_TARGETS=`aws efs describe-mount-targets \
                --file-system-id "${FS_ID}" \
                | jq --raw-output '.MountTargets[]'`
    while [ ! -z "${MOUNT_TARGETS// }" ]; do
        echo "."
        sleep 10s
        MOUNT_TARGETS=`aws efs describe-mount-targets \
                --file-system-id "${FS_ID}" \
                | jq --raw-output '.MountTargets[]'`
    done

    aws efs delete-file-system --file-system-id "${FS_ID}"
fi

################################################################
# Deleting KMS (if used)
if [ ! -z "${KMS_ALIAS// }" ]
then
    KEY_ID=$(aws kms list-aliases | jq --raw-output --arg aliasname "alias/${KMS_ALIAS// }" '.Aliases[] | select(.AliasName==$aliasname) | .TargetKeyId')
    if [ ! -z "${KEY_ID// }" ]; then
        aws kms disable-key --key-id ${KEY_ID}
        aws kms delete-alias --alias-name "alias/${KMS_ALIAS}"
        aws kms schedule-key-deletion --key-id ${KEY_ID} --pending-window-in-days 7
    fi
fi

################################################################
# Deleting Security Group
SG_ID=$(aws ec2 describe-security-groups \
                --filters "Name=vpc-id,Values=${VPC_ID}" "Name=group-name,Values=${SG_EFS_NAME}" \
                | jq --raw-output '.SecurityGroups[].GroupId')
if [ ! -z "${SG_ID// }" ]; then
    with_backoff aws ec2 delete-security-group --group-id "${SG_ID}"
fi