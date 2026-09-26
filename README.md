# Jizura Desktop

JIZURA を Wails でデスクトップアプリとして動かすプロジェクトです。

Windows x64向けの初期実装があります。固定した原作、全7言語画面、全40フォントを単一exeへ同梱し、ZIP配布物を生成できます。一部のネイティブ操作と別環境確認は引き続き検証中です。
Windows 11 / WebView2での音声付きMP4、PNG ZIP、プロジェクトJSON、再起動復元の自動実機検証があります。

## 検証状況

次の項目は未確認です。

- 大きな動画用の直接保存ダイアログによる保存と、ダイアログ上のキャンセル
- WebView2 Runtime未導入環境での起動案内
- 各言語の代表表示と原作ブラウザ版との目視比較

## 必要なもの

- Git
- mise
- Windows では WebView2 Runtime（通常は Windows 10/11 に導入済み）

mise 自体のインストール方法は公式ドキュメントを参照してください。

- Windows / Scoop: `scoop install mise`
- Windows / winget: `winget install jdx.mise`
- macOS / Linux: <https://mise.jdx.dev/installing-mise.html>

PowerShell のプロファイルへ mise の activation を追加しなくても、以下のコマンドは利用できます。

## セットアップ

```powershell
git submodule update --init --recursive
mise trust
mise install
mise run versions
mise run doctor
```

`mise.toml` では、Go、Python、Node.js、Wails CLI をプロジェクト単位で固定しています。
`mise.lock` には各 OS・CPU 向け配布物の URL とチェックサムを記録し、同じ環境を再現できるようにしています。

## 固定バージョン

- Go 1.26.5
- Python 3.14.7
- Node.js 24.21.0 LTS
- Wails v3.0.0-beta.26

## GitHub Actionsとリリース

`main` へのpush、Pull Request、Actions画面からの手動実行で、Windows上のテストとZIP生成を行います。実行結果の `windows-amd64` ArtifactからZIPと `SHA256SUMS.txt` を取得できます。Artifactの保存期間は7日です。GUI操作を伴う `probe` / `probe-ui` はCIに含めず、配布前にローカルで確認します。

リリース時は `APP_VERSION` を更新してコミット・pushし、そのコミットへ同じバージョンのタグを付けてpushします。例えば `APP_VERSION` が `0.1.0` の場合:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

タグと `APP_VERSION` が一致し、テスト・ビルドが成功すると、ZIPとSHA-256を添付した下書きReleaseが作成されます。GitHubのReleases画面でZIPを確認してから手動で公開してください。`0.1.0-dev.1` のようなバージョンはプレリリース扱いです。タグ実行をやり直した場合は下書きの添付だけを更新し、公開済みReleaseは上書きしません。

Actionsは組み込みの `GITHUB_TOKEN` を使用するため、通常は個人トークンのSecret登録は不要です。書き込み権限はタグのRelease作成ジョブだけに与えています。フォントキャッシュはコミットとマニフェストで識別し、復元後もハッシュを検証します。

Wails CLI は mise の Go backend で管理しているため、別途グローバルに `go install` する必要はありません。

## コマンド

```powershell
# プロジェクトで使われるバージョンを表示
mise run versions

# Wails と OS 依存関係を診断
mise run doctor

# mise 管理下で任意のコマンドを実行
mise exec -- go version
mise exec -- wails3 version
```

```powershell
# 固定原作とフォントからWebアセットを生成
mise run prepare

# 検証済みキャッシュだけを使い、通信せず生成
mise run prepare-offline

# アプリを開発起動
mise run dev

# Windows x64 exeを生成
mise run build

# 自動チェック
mise run check

# Windows x64 ZIP配布物を生成
mise run package

# 一時プロファイルでWebView2 APIとコーデックを確認
mise run probe

# 原作UI経由の実ファイル保存と再起動復元を確認
mise run probe-ui
```

初回の `prepare` は、固定したGoogle Fontsコミットから約325 MiBのフォントを取得します。以後は `.cache/fonts/<source_commit>/` のサイズ・SHA-256検証済みキャッシュを再利用します。旧 `.cache/fonts/source/` は、現在のロック値に一致するファイルだけがコミット別領域へ移行されます。

`mise run dev` と通常の `go run .` は開発プロファイル `%LOCALAPPDATA%\JizuraDesktop-Dev\WebView2\` を使います。`mise run build` と `mise run package` は `production` ビルドタグを付け、本番プロファイル `%LOCALAPPDATA%\JizuraDesktop\WebView2\` を使います。開発起動が配布版の設定・曲・追加フォントを変更することはありません。
