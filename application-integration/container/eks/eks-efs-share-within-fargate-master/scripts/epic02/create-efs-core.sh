#!/bin/bash

# File System Token
FS_TOKEN=$1
# KMS CMK Key Alias
KMS_ALIAS=$2
# Encryption at Rest
EFS_ENCRYPTED_AT_REST=$3

echo "#######################################################"
echo "[INFO] Creating the EFS File System"

# Checking if EFS already exists
FS_EXISTS=`aws efs describe-file-systems \
                    --creation-token ${FS_TOKEN} \
                    | jq --raw-output '.FileSystems[]'`
if [ -z "${FS_EXISTS// }" ]
then
    # Creating the EFS and getting its ID
    EFS_CMD="aws efs create-file-system \
                --creation-token ${FS_TOKEN} \
                --performance-mode generalPurpose \
                --throughput-mode bursting"

    if $EFS_ENCRYPTED_AT_REST
    then
        EFS_CMD="${EFS_CMD} --encrypted"
        
        if [ ! -z "${KMS_ALIAS// }" ]
        then
            EFS_CMD="${EFS_CMD} --kms-key-id \"alias/${KMS_ALIAS}\""
        fi
    fi 

    EFS_CMD="${EFS_CMD} | jq --raw-output '.FileSystemId'"

    FS_ID=`eval $EFS_CMD`

    # Waiting until the end of execution of the process
    while [ $(aws efs describe-file-systems \
                        --file-system-id $FS_ID \
                        | jq --raw-output --arg fsi $FS_ID \
                            '.FileSystems[] | select(.FileSystemId==$fsi) | .LifeCycleState') != "available" ]
    do
        echo "Waiting for efs $FS_ID creation..."
        sleep 5s
    done

    echo "EFS $FS_ID was sucessfully created."
else
    echo "File system already exists for this token: ${FS_TOKEN}"
fi