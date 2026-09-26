//go:build !production

package main

import "testing"

func TestDevelopmentProfileDirectory(t *testing.T) {
	if profileDirectory != "JizuraDesktop-Dev" {
		t.Fatalf("development profile = %q", profileDirectory)
	}
}
