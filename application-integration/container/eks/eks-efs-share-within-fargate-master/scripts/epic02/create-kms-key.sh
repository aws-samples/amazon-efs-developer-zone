#!/bin/bash

# KMS CMK Key Alias
KMS_ALIAS=$1

echo "#######################################################"
echo "[INFO] Creating the KMS CMK key"

KEY_ALIAS_EXISTS=`aws kms list-aliases | \
                    jq --raw-output --arg aliasname "alias/${KMS_ALIAS}" \
                        '.Aliases[] | select(.AliasName==$aliasname) | .AliasArn'`
if [ -z "${KEY_ALIAS_EXISTS// }" ]; then
    aws kms create-alias --alias-name "alias/${KMS_ALIAS}" \
        --target-key-id $(aws kms create-key --query KeyMetadata.Arn --output text)
else
    echo "A Key Alias already exists for this alias ${KMS_ALIAS}."
fi