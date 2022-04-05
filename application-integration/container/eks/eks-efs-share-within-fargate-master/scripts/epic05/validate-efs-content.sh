#!/bin/bash

BASEDIR=$(dirname "$0")

nflag=false

usage () { echo "
    -h -- Opens up this help message
    -t -- Token used for EFS creation
    -n -- Application namespace
"; }
options=':t:n:dh'
while getopts $options option
do
    case "$option" in
        t  ) FS_TOKEN=${OPTARG-$FS_TOKEN};;
        n  ) nflag=true; APP_NAMESPACE=${OPTARG-$APP_NAMESPACE};;
        h  ) usage; exit;;
        \? ) echo "Unknown option: -$OPTARG" >&2; exit 1;;
        :  ) echo "Missing option argument for -$OPTARG" >&2; exit 1;;
        *  ) echo "Unimplemented option: -$OPTARG" >&2; exit 1;;
    esac
done

#######################################
# Treating parameters
FS_TOKEN="$(sed -e 's/[[:space:]]*$//' <<<${FS_TOKEN})"
if [ -z "${FS_TOKEN// }" ]
then
    echo "-t nor FS_TOKEN env variable specified. Please inform the token used in the EFS creation..." >&2
    exit 99
fi

APP_NAMESPACE="$(sed -e 's/[[:space:]]*$//' <<<${APP_NAMESPACE})"
if ! $nflag
then
    echo "-n nor APP_NAMESPACE env variable specified, using poc-efs-eks-fargate for k8s application namespace..." >&2
    APP_NAMESPACE="poc-efs-eks-fargate"
fi

# Getting the EFS File System ID
FS_ID=`aws efs describe-file-systems \
               --creation-token ${FS_TOKEN} \
               | jq --raw-output '.FileSystems[] | .FileSystemId'`
if [ -z "${FS_ID// }" ]; then
    echo "EFS File System ID was not found for this file system creation token ${FS_TOKEN}."
    exit 98
fi
echo "Working with EFS File System ID: ${FS_ID}"

# Deleting the application components
kubectl delete pod poc-app2 -n $APP_NAMESPACE
kubectl delete pod poc-app1 -n $APP_NAMESPACE
kubectl delete pvc poc-app-pvc -n $APP_NAMESPACE
kubectl delete pv poc-app-pv

# Deploying the PV needed by validation story
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolume
metadata:
   name: poc-app-validation-pv
spec:
   capacity:
      # Required field by Kubernetes.
      # Can be any value since EFS is an elastic file system 
      # it doesn't really enforce any file system capacity.
      storage: 1Mi
   volumeMode: Filesystem
   accessModes:
      - ReadWriteMany
   persistentVolumeReclaimPolicy: Retain
   storageClassName: efs-sc
   csi:
      driver: efs.csi.aws.com
      volumeHandle: $FS_ID
EOF

# Deploying the PVC requested by validation story
kubectl apply -f $BASEDIR/claim.yaml -n $APP_NAMESPACE

# Deploying the workloads of validation story
kubectl apply -f $BASEDIR/pod-validation.yaml -n $APP_NAMESPACE

# Waiting for the deployment has been completed
while [[ $(kubectl get pod poc-app-validation -n $APP_NAMESPACE | grep Running) == "" ]]; do
   echo "Waiting for pod get Running state..."
   sleep 60s
done

# Executing the command find to show all the files inside the mapped folder
echo "Results from execution of 'find /data' on validation process pod:"
kubectl exec -ti poc-app-validation -n $APP_NAMESPACE -- find /data