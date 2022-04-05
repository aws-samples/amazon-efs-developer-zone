#!/bin/bash

nflag=false

usage () { echo "
    -h -- Opens up this help message
    -c -- EKS cluster name where the EFS will be configured
    -n -- Application namespace
"; }
options=':c:n:h'
while getopts $options option
do
    case "$option" in
        c  ) K8S_CLUSTER_NAME=${OPTARG-$K8S_CLUSTER_NAME};;
        n  ) nflag=true; APP_NAMESPACE=${OPTARG-$APP_NAMESPACE};;
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

APP_NAMESPACE="$(sed -e 's/[[:space:]]*$//' <<<${APP_NAMESPACE})"
if ! $nflag
then
    echo "-n nor APP_NAMESPACE env variable specified, using poc-efs-eks-fargate for k8s application namespace..." >&2
    APP_NAMESPACE="poc-efs-eks-fargate"
fi

if $missing_parameters
then
    exit 99
fi

# Create a Kubernetes namespace for application workloads
kubectl create namespace ${APP_NAMESPACE}

# Create a custom Fargate Profile linked to created namespace
eksctl create fargateprofile \
                --namespace "${APP_NAMESPACE}" \
                --cluster "${K8S_CLUSTER_NAME}" \
                --name "fp-${APP_NAMESPACE}"