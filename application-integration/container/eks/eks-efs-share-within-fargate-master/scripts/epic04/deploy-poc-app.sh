#!/bin/bash

BASEDIR=$(dirname "$0")

nflag=false
dflag=false

usage () { echo "
    -h -- Opens up this help message
    -t -- Token used for EFS creation
    -n -- Application namespace
    -d -- To disable EFS encryption in transit
"; }
options=':t:n:dh'
while getopts $options option
do
    case "$option" in
        t  ) FS_TOKEN=${OPTARG-$FS_TOKEN};;
        n  ) nflag=true; APP_NAMESPACE=${OPTARG-$APP_NAMESPACE};;
        d  ) dflag=true; EFS_ENCRYPTED_IN_TRANSIT=false;;
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

if ! $dflag
then
    echo "-d not specified, using true as default value for EFS encryption in transit..." >&2
    EFS_ENCRYPTED_IN_TRANSIT=true
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

if $EFS_ENCRYPTED_IN_TRANSIT
then
# Deploying the PV needed by the application
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolume
metadata:
   name: poc-app-pv
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
      volumeAttributes:
        encryptInTransit: "true"
EOF

else
# Deploying the PV needed by the application
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolume
metadata:
   name: poc-app-pv
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
      volumeAttributes:
        encryptInTransit: "false"
EOF
fi

# Deploying the PVC requested by the application
kubectl apply -f $BASEDIR/claim.yaml -n $APP_NAMESPACE

# Deploying the workloads of the application
kubectl apply -f $BASEDIR/pod1.yaml -n $APP_NAMESPACE
kubectl apply -f $BASEDIR/pod2.yaml -n $APP_NAMESPACE