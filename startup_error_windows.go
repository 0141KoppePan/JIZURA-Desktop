//go:build windows

package main

import (
	"fmt"
	"strings"

	"golang.org/x/sys/windows"
)

func showStartupError(err error) {
	message := fmt.Sprintf("JIZURA Desktopを起動できませんでした。\n\n%v", err)
	if strings.Contains(err.Error(), "WebView2") {
		message = "Microsoft Edge WebView2 Runtimeを初期化できませんでした。\n\n" +
			"未導入の場合は、Microsoft公式サイトからWebView2 Runtimeを導入してください。\n" +
			"導入済みの場合は、Runtimeの修復または更新後に再度お試しください。\n\n" +
			"詳細: " + err.Error()
	}

	text, textErr := windows.UTF16PtrFromString(message)
	caption, captionErr := windows.UTF16PtrFromString(applicationName)
	if textErr != nil || captionErr != nil {
		return
	}
	_, _ = windows.MessageBox(0, text, caption, windows.MB_OK|windows.MB_ICONERROR|windows.MB_SYSTEMMODAL)
}
