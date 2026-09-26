//go:build production

package main

import "testing"

func TestProductionProfileDirectory(t *testing.T) {
	if profileDirectory != "JizuraDesktop" {
		t.Fatalf("production profile = %q", profileDirectory)
	}
}
