#!/bin/bash

# Cluster Name
K8S_CLUSTER_NAME=$1
# Application Namespace
APP_NAMESPACE=$2

# EPIC 01 - Deleting Application Namespace, and Fargate Profile
kubectl delete namespace ${APP_NAMESPACE}

eksctl delete fargateprofile --wait \
    --cluster "${K8S_CLUSTER_NAME}" \
    --name "fp-${APP_NAMESPACE}"