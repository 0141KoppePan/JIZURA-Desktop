//go:build !windows

package main

import "log"

func showStartupError(err error) {
	log.Printf("%s: %v", applicationName, err)
}
