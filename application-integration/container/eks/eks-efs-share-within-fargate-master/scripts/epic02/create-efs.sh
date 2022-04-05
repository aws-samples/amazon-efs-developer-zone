#!/bin/bash

export AWS_PAGER=""

BASEDIR=$(dirname "$0")

sflag=false
kflag=false
dflag=false

usage () { echo "
    -h -- Opens up this help message
    -c -- EKS cluster name where the EFS will be configured
    -t -- Token for EFS creation, which guarantees creation when needed only
    -s -- Name of the security group for EFS access
    -k -- KMS CMK alias (ignored when encryption is disabled)
    -d -- To disable EFS encryption at creation process
"; }
options=':c:t:s:k:dh'
while getopts $options option
do
    case "$option" in
        c  ) K8S_CLUSTER_NAME=${OPTARG-$K8S_CLUSTER_NAME};;
        t  ) FS_TOKEN=${OPTARG-$FS_TOKEN};;
        s  ) sflag=true; SG_EFS_NAME=${OPTARG-$SG_EFS_NAME};;
        k  ) kflag=true; KMS_ALIAS=${OPTARG-$KMS_ALIAS};;
        d  ) dflag=true; EFS_ENCRYPTED_AT_REST=false;;
        h  ) usage; exit;;
        \? ) echo "Unknown option: -$OPTARG" >&2; exit 1;;
        :  ) echo "Missing option argument for -$OPTARG" >&2; exit 1;;
        *  ) echo "Unimplemented option: -$OPTARG" >&2; exit 1;;
    esac
done

#######################################
# Treating parameters
missing_parameters=false

K8S_CLUSTER_NAME="$(sed -e 's/[[:space:]]*$//' <<<${K8S_CLUSTER_NAME})"
if [ -z "${K8S_CLUSTER_NAME// }" ]
then
    echo "-c nor K8S_CLUSTER_NAME env variable specified. Please inform the EKS cluster name..." >&2
    missing_parameters=true
fi

FS_TOKEN="$(sed -e 's/[[:space:]]*$//' <<<${FS_TOKEN})"
if [ -z "${FS_TOKEN// }" ]
then
    echo "-t nor FS_TOKEN env variable specified. Please inform a token for EFS creation..." >&2
    missing_parameters=true    
fi

SG_EFS_NAME="$(sed -e 's/[[:space:]]*$//' <<<${SG_EFS_NAME})"
if ! $sflag
then
    echo "-s nor not SG_EFS_NAME env variable specified, using eks-${K8S_CLUSTER_NAME}-efs-SecurityGroup as security group name for EFS..." >&2
    SG_EFS_NAME="eks-${K8S_CLUSTER_NAME}-efs-SecurityGroup"
fi

if ! $dflag
then
    echo "-d not specified, using true as default value for EFS encrypted creation..." >&2
    EFS_ENCRYPTED_AT_REST=true
fi

KMS_ALIAS="$(sed -e 's/[[:space:]]*$//' <<<${KMS_ALIAS})"

if $missing_parameters
then
    exit 99
fi
#######################################

# Verifying that the cluster exists
K8S_EXISTS=`aws eks list-clusters \
                        | jq --raw-output --arg clustername "${K8S_CLUSTER_NAME}" \
                            '.clusters[] | select(contains($clustername)) | .'`
if [ -z "${K8S_EXISTS// }" ]; then
    echo "A Kubernetes cluster does not exist for the informed cluster name: ${K8S_CLUSTER_NAME}"
    exit 98
fi

# Getting the VPC ID from Kubernetes cluster
export VPC_ID=`aws eks describe-cluster --name $K8S_CLUSTER_NAME | jq --raw-output '.cluster.resourcesVpcConfig.vpcId'`
if [ -z "${VPC_ID// }" ]; then
    echo "VPC ID was not found for this cluster ${K8S_CLUSTER_NAME}."
    exit 97
fi
echo "Working with VPC ID: ${VPC_ID}"

# Getting the NAT Gateways IDs for discovering the private subnets
NAT_GATEWAYS=`aws ec2 describe-nat-gateways \
                        --filter "Name=vpc-id,Values=${VPC_ID}" "Name=state,Values=available" \
                            | jq --raw-output '.NatGateways[] | .NatGatewayId'`
IFS=$'\n' read -rd '' -a NAT_GATEWAYS <<<"$NAT_GATEWAYS"

# Discovering private subnets through route table (destination 0.0.0.0/0, target natgtw)
export PRIVATE_SUBNETS=()
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

if $EFS_ENCRYPTED_AT_REST && [ ! -z "${KMS_ALIAS// }" ]
then
    . $BASEDIR/create-kms-key.sh "${KMS_ALIAS}"
fi

. $BASEDIR/create-efs-core.sh "${FS_TOKEN}" "${KMS_ALIAS}" ${EFS_ENCRYPTED_AT_REST}
. $BASEDIR/create-efs-sg.sh "${K8S_CLUSTER_NAME}" "${SG_EFS_NAME}"
. $BASEDIR/create-efs-mount-target.sh "${K8S_CLUSTER_NAME}" "${FS_TOKEN}" "${SG_EFS_NAME}"