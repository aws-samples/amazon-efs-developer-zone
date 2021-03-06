package base

import (
	"github.com/kubeflow/manifests/tests"
	"testing"
)

func TestKustomize(t *testing.T) {
	testCase := &tests.KustomizeTestCase{
		Package: "../../../../../distributions/aws/aws-alb-ingress-controller/base",
		Expected: "test_data/expected",
	}

	tests.RunTestCase(t, testCase)
}