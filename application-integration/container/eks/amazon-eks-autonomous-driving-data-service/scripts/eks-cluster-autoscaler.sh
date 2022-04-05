#!/bin/bash
#Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# 
#Permission is hereby granted, free of charge, to any person obtaining a copy of this
#software and associated documentation files (the "Software"), to deal in the Software
#without restriction, including without limitation the rights to use, copy, modify,
#merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
#permit persons to whom the Software is furnished to do so.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
#PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
#OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

scripts_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
[[ -z "${eks_cluster_name}" ]] && echo "eks_cluster_name env variable is required" && exit 1
[[ -z "${eks_cluster_autoscaler_role_arn}" ]] && echo "eks_cluster_autoscaler_role_arn required" && exit 1
[[ -z "${cluster_autoscaler_image_tag}" ]] && cluster_autoscaler_image_tag="v1.21.0" 


kubectl apply -f https://raw.githubusercontent.com/kubernetes/autoscaler/master/cluster-autoscaler/cloudprovider/aws/examples/cluster-autoscaler-autodiscover.yaml

cat >cluster-autoscaler-serviceaccount-patch.json <<EOL
{"metadata":{"annotations":{"eks.amazonaws.com/role-arn": "${eks_cluster_autoscaler_role_arn}"}}}
EOL

kubectl patch ServiceAccount cluster-autoscaler -n kube-system --patch "$(cat cluster-autoscaler-serviceaccount-patch.json)" 
  
cat >cluster-autoscaler-deployment-patch.json <<EOL
{"spec": { "template": { "metadata":{"annotations":{"cluster-autoscaler.kubernetes.io/safe-to-evict": "false"}}, "spec": { "containers": [{ "image": "k8s.gcr.io/autoscaling/cluster-autoscaler:${cluster_autoscaler_image_tag}", "name": "cluster-autoscaler", "resources": { "requests": {"cpu": "100m", "memory": "300Mi"}}, "command": [ "./cluster-autoscaler", "--v=4", "--stderrthreshold=info", "--cloud-provider=aws", "--skip-nodes-with-local-storage=false", "--expander=least-waste", "--node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/${eks_cluster_name}", "--balance-similar-node-groups", "--skip-nodes-with-system-pods=false" ]}]}}}}
EOL

kubectl -n kube-system patch deployment cluster-autoscaler --patch "$(cat  cluster-autoscaler-deployment-patch.json)"
