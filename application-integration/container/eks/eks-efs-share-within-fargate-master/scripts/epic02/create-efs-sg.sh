#!/bin/bash

# Cluster Name
K8S_CLUSTER_NAME=$1
# Security Group Name
SG_EFS_NAME=$2

echo "#######################################################"
echo "[INFO] Creating the Security Group for the EFS"

# Checking if EFS already exists
SG_EXISTS=`aws ec2 describe-security-groups \
                    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=group-name,Values=${SG_EFS_NAME}" \
                    | jq --raw-output '.SecurityGroups[]'`
if [ -z "${SG_EXISTS// }" ]; then
    # Creating the SG and getting its ID
    SG_ID=`aws ec2 create-security-group \
                            --group-name "${SG_EFS_NAME}" \
                            --description "Allow EKS Cluster to access EFS File System" \
                            --vpc-id ${VPC_ID} \
                            --tag-specifications "ResourceType=security-group,Tags=[{Key=Name,Value=${SG_EFS_NAME}}]" \
                            | jq --raw-output '.GroupId'`
    echo "Security group was created and its ID is: ${SG_ID}"
                        
    # Getting the cluster's VPC CIDR block range
    VPC_CIDR=`aws ec2 describe-vpcs --vpc-ids "${VPC_ID}" \
                    | jq --raw-output --arg vpcid "${VPC_ID}" \
                        '.Vpcs[] | select(.VpcId==$vpcid) | .CidrBlock'`
    echo "Working with VPC CIDR block range: ${VPC_CIDR}"

    # Add the inbound rule for protocol TCP, port 2049, and having source as Kubernetes cluster VPC private subnets' CIDR block ranges
    # Getting the CIDR of private subnets
    FILTER_SUBNET_IDS=`printf "%s," "${PRIVATE_SUBNETS[@]}" | cut -d "," -f 1-${#PRIVATE_SUBNETS[@]}`
    if [ ! -z "${FILTER_SUBNET_IDS// }" ]; then
        INBOUND_RULE_ADD_CMD="aws ec2 authorize-security-group-ingress --group-id \"${SG_ID}\" --ip-permissions IpProtocol=tcp,FromPort=2049,ToPort=2049,IpRanges=["

        PRIVATE_SUBNET_CIDRS=`aws ec2 describe-subnets --filters "Name=subnet-id,Values=${FILTER_SUBNET_IDS}" | jq --raw-output '.Subnets[].CidrBlock'`
        IFS=$'\n' read -rd '' -a PRIVATE_SUBNET_CIDRS <<<"$PRIVATE_SUBNET_CIDRS"

        # For each private subnet CIDR
        for subnetcidrip in "${PRIVATE_SUBNET_CIDRS[@]}"
        do
            INBOUND_RULE_ADD_CMD="${INBOUND_RULE_ADD_CMD}{CidrIp=${subnetcidrip}},"
        done

        INBOUND_RULE_ADD_CMD=`echo $INBOUND_RULE_ADD_CMD | sed 's/.$//'`
        INBOUND_RULE_ADD_CMD="${INBOUND_RULE_ADD_CMD}]"

        eval $INBOUND_RULE_ADD_CMD
    fi

    echo "Attached inbound rule (protocol | port | source) as: tcp | 2049 | ${PRIVATE_SUBNET_CIDRS[@]}"

else
    echo "Security Group already exists for this VPC ${VPC_ID} and named ${SG_EFS_NAME}."
fi