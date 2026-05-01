# SteamCMD Workshop Downloader

コマンドって覚えないといけないからGUIになるよね。

<img width="1297" height="1032" alt="image" src="https://github.com/user-attachments/assets/bfb68caf-7517-4a98-87ad-2923887e52b5" />

### コマンド操作を卒業しよう
SteamCMDは強力ですが、コマンドをいちいち覚えたり入力したりするのは大変です。
このツールは、そんな面倒な操作をすべてGUIにまとめました。URLを貼ってボタンを押すだけで、誰でも簡単にワークショップアイテムをダウンロードできます。

## 特徴

- **覚える必要なし**: 複雑なコマンドの代わりに、分かりやすいボタンと入力欄で操作できます。
- **URLを貼るだけ**: ワークショップのURLから ID を自動で解析します。
- **まとめて管理**: 複数のアイテムもスムーズにダウンロード。
- **どこでも使える**: 日本語・英語対応。設定もポータブル。

## 動作要件

- **OS**: Windows (推奨)
- **SteamCMD**: 本ツールの動作には [SteamCMD](https://developer.valvesoftware.com/wiki/SteamCMD:ja) が必要です。

## 使い方

1. `SteamCMD` を用意します。
2. ツールを起動して `SteamCMD.exe` の場所を教えてあげます。
3. ダウンロードしたいURLを入力して、ダウンロードボタンを押すだけ！

## 開発者向け（ソースコードからの実行）

### 環境構築
```bash
pip install PySide6
```

### 実行方法
```bash
python steamCMDGUI.py
```

## ライセンス
MIT License

## 作者
[Ikumyon](https://github.com/Ikumyon)
