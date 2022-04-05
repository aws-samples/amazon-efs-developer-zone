#!/bin/bash

# Cluster Name
K8S_CLUSTER_NAME=$1
# File System Token
FS_TOKEN=$2
# Security Group Name
SG_EFS_NAME=$3

echo "#######################################################"
echo "[INFO] Creating the Mount Target for the EFS"

# Getting the Security Group ID
SG_ID=`aws ec2 describe-security-groups \
                --filters "Name=vpc-id,Values=${VPC_ID}" "Name=group-name,Values=${SG_EFS_NAME}" \
                | jq --raw-output '.SecurityGroups[] | .GroupId'`
if [ -z "${SG_ID// }" ]; then
    echo "Security Group ID was not found for this VPC ${VPC_ID} and Security Group name ${SG_EFS_NAME}."
    exit 96
fi
echo "Working with Security Group ID: ${SG_ID}"

# Getting the EFS File System ID
FS_ID=`aws efs describe-file-systems \
                --creation-token ${FS_TOKEN} \
                | jq --raw-output '.FileSystems[] | .FileSystemId'`
if [ -z "${FS_ID// }" ]; then
    echo "EFS File System ID was not found for this file system creation token ${FS_TOKEN}."
    exit 95
fi
echo "Working with EFS File System ID: ${FS_ID}"

# Creating the mount target per private subnet
for pvtsubnet in "${PRIVATE_SUBNETS[@]}"
do
    MNT_TGT_ID=`aws efs describe-mount-targets \
                        --file-system-id "${FS_ID}" \
                            | jq --raw-output --arg subnetid "${pvtsubnet}" \
                            '.MountTargets[] | select(.SubnetId==$subnetid) | .MountTargetId'`
    # Does not exist yet
    if [ ! -z "${MNT_TGT_ID// }" ]; then
        echo "Mouting target ${MNT_TGT_ID} already exists for file system ${FS_ID} into subnet ${pvtsubnet}."

    else
        MNT_TGT_ID=`aws efs create-mount-target \
                                --file-system-id "${FS_ID}" \
                                --subnet-id "${pvtsubnet}" \
                                --security-group "${SG_ID}" \
                                | jq --raw-output '.MountTargetId'`

        # Waiting until the end of execution of the process
        while [ $(aws efs describe-mount-targets \
                            --mount-target-id "${MNT_TGT_ID}" \
                            | jq --raw-output \
                                '.MountTargets[] | .LifeCycleState') != "available" ]; do
            echo "Waiting for mouting target $MNT_TGT_ID creation..."
            sleep 40s
        done

        echo "Created mouting target ${MNT_TGT_ID} for file system ${FS_ID} into subnet ${pvtsubnet} with security group ${SG_ID}."
    fi
done