package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestUserDataPathUsesStableLocalDirectory(t *testing.T) {
	base := t.TempDir()

	got, err := ensureUserDataPath(base)
	if err != nil {
		t.Fatal(err)
	}

	want := filepath.Join(base, profileDirectory, "WebView2")
	if got != want {
		t.Fatalf("userDataPath() = %q, want %q", got, want)
	}
	if info, err := os.Stat(got); err != nil || !info.IsDir() {
		t.Fatalf("user data directory was not created: info=%v err=%v", info, err)
	}
}

func TestWindowsOptionsAcceptsOnlyNumericDiagnosticPort(t *testing.T) {
	t.Setenv("JIZURA_WEBVIEW2_BLOCK_NETWORK", "")
	t.Setenv("JIZURA_WEBVIEW2_DEBUG_PORT", "9222")
	options := windowsOptions(`C:\data`)
	if options.WebviewUserDataPath != `C:\data` {
		t.Fatalf("unexpected WebView2 data path: %q", options.WebviewUserDataPath)
	}
	if len(options.AdditionalBrowserArgs) != 1 || options.AdditionalBrowserArgs[0] != "--remote-debugging-port=9222" {
		t.Fatalf("unexpected diagnostic arguments: %#v", options.AdditionalBrowserArgs)
	}

	t.Setenv("JIZURA_WEBVIEW2_DEBUG_PORT", "9222 --disable-web-security")
	options = windowsOptions(`C:\data`)
	if len(options.AdditionalBrowserArgs) != 0 {
		t.Fatalf("unsafe diagnostic arguments were accepted: %#v", options.AdditionalBrowserArgs)
	}
}

func TestWindowsOptionsCanBlockOnlyTheTestWebViewNetwork(t *testing.T) {
	t.Setenv("JIZURA_WEBVIEW2_DEBUG_PORT", "")
	t.Setenv("JIZURA_WEBVIEW2_BLOCK_NETWORK", "1")
	options := windowsOptions(`C:\data`)
	if len(options.AdditionalBrowserArgs) != 2 {
		t.Fatalf("unexpected isolation arguments: %#v", options.AdditionalBrowserArgs)
	}
	if options.AdditionalBrowserArgs[0] != "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE wails.localhost" {
		t.Fatalf("unexpected resolver isolation: %q", options.AdditionalBrowserArgs[0])
	}
}
