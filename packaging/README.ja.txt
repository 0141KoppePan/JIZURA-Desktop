JIZURA Desktop @APP_VERSION@
============================

原作JIZURA @UPSTREAM_VERSION@を、Windowsデスクトップアプリとして利用するための開発版です。

動作環境
--------

- Windows x64
- Microsoft Edge WebView2 Runtime

起動方法
--------

1. ZIPを任意のフォルダーへ完全に展開します。
2. JIZURA-Desktop.exeを起動します。

開発ツールやインターネット接続は必要ありません。フォントはアプリに同梱されています。
WebView2 Runtimeがない場合は、Microsoft公式サイトから導入してください。アプリによる自動導入は行いません。

保存データ
----------

設定、自動保存、読み込んだ曲や追加フォントのアプリ内コピーは、次の場所に保存されます。

%LOCALAPPDATA%\JizuraDesktop\

動画、画像、プロジェクトJSONなど、利用者が書き出したファイルは選択した場所に保存されます。

アンインストール
----------------

1. JIZURA Desktopを終了します。
2. ZIPを展開したフォルダーを削除します。
3. 設定と自動保存も消す場合だけ、%LOCALAPPDATA%\JizuraDesktop\ を削除します。

3を行うと、アプリ内に保存された曲や追加フォントのコピーも削除されます。元のファイルや、別の場所へ書き出したファイルは削除されません。共有のWebView2 Runtimeは削除しないでください。

ライセンス
----------

原作JIZURA、mp4-muxer、同梱フォントのライセンスとメタデータは licenses フォルダーにあります。
