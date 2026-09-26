package main

import (
	"embed"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strconv"

	"github.com/wailsapp/wails/v3/pkg/application"
)

const (
	applicationName = "JIZURA Desktop"
)

// The preparation task replaces everything except .gitkeep with the web
// assets generated from the pinned upstream source.
//
//go:embed all:frontend/dist
var assets embed.FS

func main() {
	webviewDataPath, err := userDataPath()
	if err != nil {
		showStartupError(fmt.Errorf("アプリデータ保存先を準備できませんでした: %w", err))
		return
	}

	app := application.New(application.Options{
		Name:        applicationName,
		Description: "JIZURA lyric motion video maker",
		Assets: application.AssetOptions{
			Handler: application.AssetFileServerFS(assets),
		},
		Windows:      windowsOptions(webviewDataPath),
		ErrorHandler: handleApplicationError,
	})

	app.Window.NewWithOptions(application.WebviewWindowOptions{
		Name:             "main",
		Title:            applicationName,
		Width:            1440,
		Height:           960,
		MinWidth:         960,
		MinHeight:        640,
		InitialPosition:  application.WindowCentered,
		BackgroundColour: application.NewRGB(10, 10, 12),
		URL:              "/",
	})

	if err := app.Run(); err != nil {
		showStartupError(err)
	}
}

func userDataPath() (string, error) {
	base, err := os.UserCacheDir()
	if err != nil {
		return "", err
	}
	return ensureUserDataPath(base)
}

func ensureUserDataPath(base string) (string, error) {
	path := filepath.Join(base, profileDirectory, "WebView2")
	if err := os.MkdirAll(path, 0o700); err != nil {
		return "", err
	}
	return path, nil
}

func windowsOptions(webviewDataPath string) application.WindowsOptions {
	options := application.WindowsOptions{WebviewUserDataPath: webviewDataPath}
	port, err := strconv.Atoi(os.Getenv("JIZURA_WEBVIEW2_DEBUG_PORT"))
	if err == nil && port > 0 && port <= 65535 {
		options.AdditionalBrowserArgs = append(options.AdditionalBrowserArgs, fmt.Sprintf("--remote-debugging-port=%d", port))
	}
	if os.Getenv("JIZURA_WEBVIEW2_BLOCK_NETWORK") == "1" {
		// Test-only, process-scoped isolation. The internal Wails origin is exempt;
		// no system firewall or shared WebView2 installation is changed.
		options.AdditionalBrowserArgs = append(
			options.AdditionalBrowserArgs,
			"--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE wails.localhost",
			"--disable-background-networking",
		)
	}
	return options
}

func handleApplicationError(err error) {
	var fatal *application.FatalError
	if errors.As(err, &fatal) {
		showStartupError(err)
		return
	}
	log.Printf("JIZURA Desktop: %v", err)
}
