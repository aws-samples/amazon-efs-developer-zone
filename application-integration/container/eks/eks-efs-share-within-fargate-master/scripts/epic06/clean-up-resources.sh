#!/bin/bash

BASEDIR=$(dirname "$0")

nflag=false
sflag=false
kflag=false

usage () { echo "
    -h -- Opens up this help message
    -c -- EKS cluster name where the EFS will be configured
    -t -- Token for EFS creation, which guarantees creation when needed only
    -n -- Application namespace
    -s -- Name of the security group for EFS access
    -k -- KMS CMK alias (ignored when encryption is disabled)
"; }
options=':c:t:n:s:k:h'
while getopts $options option
do
    case "$option" in
        c  ) K8S_CLUSTER_NAME=${OPTARG-$K8S_CLUSTER_NAME};;
        t  ) FS_TOKEN=${OPTARG-$FS_TOKEN};;
        n  ) nflag=true; APP_NAMESPACE=${OPTARG-$APP_NAMESPACE};;
        s  ) sflag=true; SG_EFS_NAME=${OPTARG-$SG_EFS_NAME};;
        k  ) kflag=true; KMS_ALIAS=${OPTARG-$KMS_ALIAS};;
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

APP_NAMESPACE="$(sed -e 's/[[:space:]]*$//' <<<${APP_NAMESPACE})"
if ! $nflag
then
    echo "-n nor APP_NAMESPACE env variable specified, using poc-efs-eks-fargate for k8s application namespace..." >&2
    APP_NAMESPACE="poc-efs-eks-fargate"
fi

KMS_ALIAS="$(sed -e 's/[[:space:]]*$//' <<<${KMS_ALIAS})"

if $missing_parameters
then
    exit 99
fi
#######################################

$BASEDIR/clean-up-epic05.sh "${APP_NAMESPACE}"
$BASEDIR/clean-up-epic04.sh "${APP_NAMESPACE}"
$BASEDIR/clean-up-epic03.sh
$BASEDIR/clean-up-epic02.sh "${K8S_CLUSTER_NAME}" "${SG_EFS_NAME}" "${FS_TOKEN}" "${KMS_ALIAS}"
$BASEDIR/clean-up-epic01.sh "${K8S_CLUSTER_NAME}" "${APP_NAMESPACE}"