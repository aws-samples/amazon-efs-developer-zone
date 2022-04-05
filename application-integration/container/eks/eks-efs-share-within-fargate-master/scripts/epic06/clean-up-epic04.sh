#!/bin/bash

# Application Namespace
APP_NAMESPACE=$1

echo "########################################################"
echo "EPIC 04 - Deleting the application components"

kubectl delete pod poc-app2 -n $APP_NAMESPACE
kubectl delete pod poc-app1 -n $APP_NAMESPACE
kubectl delete pvc poc-app-pvc -n $APP_NAMESPACE
kubectl delete pv poc-app-pv