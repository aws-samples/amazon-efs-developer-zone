#!/bin/bash

BASEDIR=$(dirname "$0")

# Deploy Amazon EFS CSI driver into the cluster
kubectl \
    apply -f \
    https://raw.githubusercontent.com/kubernetes-sigs/aws-efs-csi-driver/release-1.0/deploy/kubernetes/base/csidriver.yaml

# Deploy the Storage Class into the cluster
kubectl apply -f $BASEDIR/storage-class.yaml