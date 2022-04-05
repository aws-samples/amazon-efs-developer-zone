#!/bin/bash

# Application Namespace
APP_NAMESPACE=$1

echo "########################################################"
echo "EPIC 05 - Deleting the application validation components"

kubectl delete pod poc-app-validation -n $APP_NAMESPACE
kubectl delete pvc poc-app-validation-pvc -n $APP_NAMESPACE
kubectl delete pv poc-app-validation-pv