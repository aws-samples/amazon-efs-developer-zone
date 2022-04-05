#!/bin/bash

echo "########################################################"
echo "EPIC 03 - Deleting Storage Class and Amazon EFS CSI Driver"

kubectl delete storageclass efs-sc

kubectl \
    delete -f \
    https://raw.githubusercontent.com/kubernetes-sigs/aws-efs-csi-driver/release-1.0/deploy/kubernetes/base/csidriver.yaml