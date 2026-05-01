import sys
import os
import ctypes

# Windowsのタスクバーアイコンを正しく表示させるための設定
try:
    myappid = u'myon.steamworkshopdownloader.v1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

import re
import json
import base64
from urllib.parse import urlparse, parse_qs

from PySide6.QtCore import QProcess, Qt, QUrl, QTranslator, QCoreApplication
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QMessageBox,
    QCheckBox,
    QGroupBox,
    QComboBox,
)


def extract_steam_ids(text: str) -> dict:
    """
    SteamのURLまたはテキストから Workshop ID と AppID を抽出する。
    """
    text = text.strip()
    results = {"workshop_id": "", "app_id": ""}

    if not text:
        return results

    # URLの場合の解析
    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        params = parse_qs(parsed.query)
        
        # クエリパラメータから抽出 (?id=... / ?appid=...)
        if "id" in params:
            results["workshop_id"] = params["id"][0]
        if "appid" in params:
            results["app_id"] = params["appid"][0]
            
        # パスから AppID を抽出 (/app/12345/)
        app_match = re.search(r"/app/(\d+)", text)
        if app_match:
            results["app_id"] = app_match.group(1)

    # テキスト中から ID を探す (id=... / appid=...)
    if not results["workshop_id"]:
        ws_match = re.search(r"id=(\d+)", text)
        if ws_match:
            results["workshop_id"] = ws_match.group(1)
        elif text.isdigit():
            results["workshop_id"] = text

    if not results["app_id"]:
        app_match = re.search(r"appid=(\d+)", text)
        if app_match:
            results["app_id"] = app_match.group(1)

    return results


class SteamCMDGui(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(self.tr("SteamCMD Workshop Downloader"))
        self.resize(850, 650)

        self.process = QProcess(self)
        self.translator = QTranslator(self)
        self._init_config_path()

        # アイコンの設定（内蔵または外置き）
        icon_path = os.path.join(self.bundle_dir, "icon.png")
        if not os.path.exists(icon_path):
            # 万が一内蔵になければ外置きを探す
            icon_path = os.path.join(self.base_dir, "icon.png")

        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.build_ui()
        self.load_settings()
        self.connect_signals()

    def _init_config_path(self):
        """パスの決定（内蔵リソースと外部設定ファイルの区別）"""
        if getattr(sys, 'frozen', False):
            # exeの隣（設定ファイル、翻訳フォルダ用）
            self.base_dir = os.path.dirname(sys.executable)
            # exeの内部（同封されたアイコン用）
            self.bundle_dir = sys._MEIPASS
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            self.bundle_dir = self.base_dir

        self.config_file = os.path.join(self.base_dir, "config.json")

    def build_ui(self):
        layout = QVBoxLayout(self)

        # SteamCMD設定
        self.cmd_group = QGroupBox()
        cmd_grid = QGridLayout(self.cmd_group)
        self.steamcmd_path_edit = QLineEdit()
        self.browse_steamcmd_btn = QPushButton()
        self.steamcmd_label = QLabel()
        
        # 言語選択（動的スキャン）
        self.lang_label = QLabel()
        self.lang_combo = QComboBox()
        self._scan_languages()

        cmd_grid.addWidget(self.steamcmd_label, 0, 0)
        cmd_grid.addWidget(self.steamcmd_path_edit, 0, 1)
        cmd_grid.addWidget(self.browse_steamcmd_btn, 0, 2)
        cmd_grid.addWidget(self.lang_label, 1, 0)
        cmd_grid.addWidget(self.lang_combo, 1, 1, 1, 2)
        layout.addWidget(self.cmd_group)

        # ダウンロード設定
        self.dl_group = QGroupBox()
        dl_grid = QGridLayout(self.dl_group)
        
        self.app_id_label = QLabel()
        self.app_id_edit = QLineEdit()
        self.workshop_input_label = QLabel()
        self.workshop_input_edit = QLineEdit()
        self.workshop_id_label = QLabel()
        self.workshop_id_edit = QLineEdit()
        self.output_dir_label = QLabel()
        self.output_dir_edit = QLineEdit()
        self.browse_output_btn = QPushButton()
        
        self.anonymous_check = QCheckBox()
        self.username_label = QLabel()
        self.username_edit = QLineEdit()
        self.password_label = QLabel()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)

        dl_grid.addWidget(self.app_id_label, 0, 0)
        dl_grid.addWidget(self.app_id_edit, 0, 1, 1, 2)
        dl_grid.addWidget(self.workshop_id_label, 1, 0)
        dl_grid.addWidget(self.workshop_id_edit, 1, 1, 1, 2)
        dl_grid.addWidget(self.output_dir_label, 2, 0)
        dl_grid.addWidget(self.output_dir_edit, 2, 1)
        dl_grid.addWidget(self.browse_output_btn, 2, 2)
        dl_grid.addWidget(self.anonymous_check, 3, 1, 1, 2)
        dl_grid.addWidget(self.username_label, 4, 0)
        dl_grid.addWidget(self.username_edit, 4, 1, 1, 2)
        dl_grid.addWidget(self.password_label, 5, 0)
        dl_grid.addWidget(self.password_edit, 5, 1, 1, 2)
        layout.addWidget(self.dl_group)

        # 操作ボタン
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton(self.tr("ダウンロード開始"))
        self.stop_btn = QPushButton(self.tr("停止"))
        self.stop_btn.setEnabled(False)
        self.open_dir_btn = QPushButton(self.tr("保存先を開く"))
        self.clear_log_btn = QPushButton(self.tr("ログ消去"))
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.open_dir_btn)
        btn_layout.addWidget(self.clear_log_btn)
        layout.addLayout(btn_layout)

        # ログエリア
        self.log_label = QLabel()
        layout.addWidget(self.log_label)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        layout.addWidget(self.log_edit, stretch=1)

        # SteamCMD入力
        self.in_group = QGroupBox()
        in_layout = QHBoxLayout(self.in_group)
        self.cmd_input_edit = QLineEdit()
        self.send_cmd_btn = QPushButton()
        in_layout.addWidget(self.cmd_input_edit)
        in_layout.addWidget(self.send_cmd_btn)
        layout.addWidget(self.in_group)

        # ステータスバー
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        # 初回のテキストセット
        self.retranslate_ui()

    def retranslate_ui(self):
        """UIのテキストを一括設定・更新する"""
        self.setWindowTitle(self.tr("SteamCMD Workshop Downloader"))
        
        self.cmd_group.setTitle(self.tr("SteamCMD設定"))
        self.steamcmd_label.setText(self.tr("SteamCMD.exe"))
        self.browse_steamcmd_btn.setText(self.tr("参照"))
        self.lang_label.setText(self.tr("言語 (Language)"))

        self.dl_group.setTitle(self.tr("Workshopダウンロード設定"))
        self.app_id_label.setText(self.tr("AppID / URL"))
        self.workshop_id_label.setText(self.tr("Workshop ID / URL"))
        self.output_dir_label.setText(self.tr("保存先"))
        self.browse_output_btn.setText(self.tr("参照"))
        
        self.app_id_edit.setPlaceholderText(self.tr("ID または URL (例: https://steamcommunity.com/app/236850/)"))
        self.workshop_id_edit.setPlaceholderText(self.tr("ID または URL (例: https://steamcommunity.com/sharedfiles/filedetails/?id=...)"))
        
        self.anonymous_check.setText(self.tr("anonymousでログイン"))
        self.username_label.setText(self.tr("ユーザー名"))
        self.username_edit.setPlaceholderText(self.tr("ユーザー名"))
        self.password_label.setText(self.tr("パスワード"))
        self.password_edit.setPlaceholderText(self.tr("パスワード"))

        self.start_btn.setText(self.tr("ダウンロード開始"))
        self.stop_btn.setText(self.tr("停止"))
        self.open_dir_btn.setText(self.tr("保存先を開く"))
        self.clear_log_btn.setText(self.tr("ログ消去"))

        self.log_label.setText(self.tr("ログ"))
        self.in_group.setTitle(self.tr("SteamCMD入力 (認証コード送信など)"))
        self.cmd_input_edit.setPlaceholderText(self.tr("コマンドまたは認証コードを入力..."))
        self.send_cmd_btn.setText(self.tr("送信"))
        
        # 現在の状態に応じたステータス
        if self.process.state() == QProcess.NotRunning:
            self.status_label.setText(self.tr("待機中"))
        else:
            self.status_label.setText(self.tr("実行中..."))

    def connect_signals(self):
        # ボタン系
        self.browse_steamcmd_btn.clicked.connect(self.select_steamcmd)
        self.browse_output_btn.clicked.connect(self.select_output_dir)
        self.start_btn.clicked.connect(self.start_download)
        self.stop_btn.clicked.connect(self.stop_process)
        self.open_dir_btn.clicked.connect(self.open_output_dir)
        self.clear_log_btn.clicked.connect(self.log_edit.clear)
        self.send_cmd_btn.clicked.connect(self.send_command)
        self.cmd_input_edit.returnPressed.connect(self.send_command)

        # 入力連動系 (URLからIDを抽出)
        self.app_id_edit.textChanged.connect(self.on_app_id_changed)
        self.workshop_id_edit.textChanged.connect(self.on_workshop_id_changed)
        self.anonymous_check.toggled.connect(self.toggle_login_fields)
        self.lang_combo.currentIndexChanged.connect(self.change_language)

        # 即時保存用
        edits = [
            self.steamcmd_path_edit, self.app_id_edit, self.workshop_id_edit,
            self.output_dir_edit, self.username_edit, self.password_edit
        ]
        for edit in edits:
            edit.textChanged.connect(self.save_settings)
        self.anonymous_check.toggled.connect(self.save_settings)

        # プロセス関連
        self.process.readyReadStandardOutput.connect(self.read_stdout)
        self.process.readyReadStandardError.connect(self.read_stderr)
        self.process.started.connect(self.on_process_started)
        self.process.finished.connect(self.on_process_finished)
        self.process.errorOccurred.connect(self.on_process_error)

    def _encode_password(self, password):
        return base64.b64encode(password.encode("utf-8")).decode("utf-8")

    def _decode_password(self, encoded):
        try:
            return base64.b64decode(encoded.encode("utf-8")).decode("utf-8")
        except:
            return encoded

    def load_settings(self):
        if not os.path.exists(self.config_file): return
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                conf = json.load(f)
            self.steamcmd_path_edit.setText(conf.get("steamcmd_path", "steamcmd.exe"))
            self.output_dir_edit.setText(conf.get("output_dir", ""))
            self.app_id_edit.setText(conf.get("app_id", ""))
            self.username_edit.setText(conf.get("username", ""))
            self.password_edit.setText(self._decode_password(conf.get("password", "")))
            is_anon = conf.get("anonymous", True)
            self.anonymous_check.setChecked(is_anon)
            self.toggle_login_fields(is_anon)
            
            # 言語設定の復元
            lang = conf.get("language", "ja")
            index = self.lang_combo.findData(lang)
            if index >= 0:
                self.lang_combo.setCurrentIndex(index)
                # 初回の言語切り替え（change_language内でsave_settingsが呼ばれるのを防ぐため信号を切る）
                self.lang_combo.blockSignals(True)
                self.change_language()
                self.lang_combo.blockSignals(False)
        except Exception as e:
            self.append_log(self.tr("設定の読み取りエラー: {0}").format(e))

    def save_settings(self):
        conf = {
            "steamcmd_path": self.steamcmd_path_edit.text().strip(),
            "output_dir": self.output_dir_edit.text().strip(),
            "app_id": self.app_id_edit.text().strip(),
            "username": self.username_edit.text().strip(),
            "password": self._encode_password(self.password_edit.text()),
            "anonymous": self.anonymous_check.isChecked(),
            "language": self.lang_combo.currentData(),
        }
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(conf, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.append_log(self.tr("設定の保存エラー: {0}").format(e))

    def change_language(self):
        """言語を切り替える"""
        lang_code = self.lang_combo.currentData()
        qm_file = os.path.join(self.base_dir, "localization", f"i18n_{lang_code}.qm")
        
        app = QApplication.instance()
        if os.path.exists(qm_file):
            if self.translator.load(qm_file):
                app.installTranslator(self.translator)
        else:
            # 日本語（ソース）またはファイルがない場合は翻訳解除
            app.removeTranslator(self.translator)
        
        self.retranslate_ui()
        if not self.lang_combo.signalsBlocked():
            self.save_settings()

    def _scan_languages(self):
        """ディレクトリ内の i18n_*.qm を探してコンボボックスに追加する"""
        self.lang_combo.clear()
        # デフォルト（ソース言語）として日本語を追加
        self.lang_combo.addItem("日本語", "ja")

        loc_dir = os.path.join(self.base_dir, "localization")
        if not os.path.exists(loc_dir): return

        temp_translator = QTranslator()
        for filename in os.listdir(loc_dir):
            if filename.startswith("i18n_") and filename.endswith(".qm"):
                lang_code = filename[5:-3] # "i18n_en.qm" -> "en"
                if lang_code == "ja": continue # jaは既に追加済み

                path = os.path.join(loc_dir, filename)
                if temp_translator.load(path):
                    # 翻訳ファイルから言語名を取得。取れない場合はコードを表示
                    lang_name = temp_translator.translate("SteamCMDGui", "LanguageName")
                    if not lang_name or lang_name == "LanguageName":
                        lang_name = lang_code.upper()
                    self.lang_combo.addItem(lang_name, lang_code)

    def update_ids_from_input(self):
        txt = self.workshop_input_edit.text() if hasattr(self, "workshop_input_edit") else ""
        ids = extract_steam_ids(txt)
        if ids["workshop_id"]: self.workshop_id_edit.setText(ids["workshop_id"])
        if ids["app_id"]: self.app_id_edit.setText(ids["app_id"])

    def on_app_id_changed(self):
        txt = self.app_id_edit.text().strip()
        if txt.startswith("http"):
            ids = extract_steam_ids(txt)
            if ids["app_id"]:
                self.app_id_edit.setText(ids["app_id"])
        self.save_settings()

    def on_workshop_id_changed(self):
        txt = self.workshop_id_edit.text().strip()
        if txt.startswith("http"):
            ids = extract_steam_ids(txt)
            if ids["workshop_id"]:
                self.workshop_id_edit.setText(ids["workshop_id"])
            # Workshop URLに AppID も含まれている場合はついでに埋める
            if ids["app_id"] and not self.app_id_edit.text():
                self.app_id_edit.setText(ids["app_id"])
        self.save_settings()

    def toggle_login_fields(self, checked):
        self.username_edit.setEnabled(not checked)
        self.password_edit.setEnabled(not checked)

    def append_log(self, text):
        self.log_edit.appendPlainText(text)
        self.log_edit.verticalScrollBar().setValue(self.log_edit.verticalScrollBar().maximum())

    def select_steamcmd(self):
        path, _ = QFileDialog.getOpenFileName(self, "steamcmd.exeを選択", "", "SteamCMD (steamcmd.exe);;All Files (*)")
        if path: self.steamcmd_path_edit.setText(path)

    def select_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "保存先フォルダを選択")
        if path: self.output_dir_edit.setText(path)

    def start_download(self):
        if self.process.state() != QProcess.NotRunning: return
        if not self.validate_inputs(): return

        self.save_settings()
        path = self.steamcmd_path_edit.text().strip()
        args = self._build_args()

        self.log_edit.clear()
        self.append_log(self.tr("=== SteamCMD 起動 ==="))
        self.append_log(self.tr("SteamCMD: {0}").format(path))
        self.append_log(self.tr("Arguments: {0}").format(self._get_masked_args_str(args)))
        self.append_log("")

        self.status_label.setText(self.tr("実行中..."))
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.process.setProgram(path)
        self.process.setArguments(args)
        self.process.start()

    def _build_args(self):
        args = ["+force_install_dir", self.output_dir_edit.text().strip()]
        if self.anonymous_check.isChecked():
            args += ["+login", "anonymous"]
        else:
            args += ["+login", self.username_edit.text().strip()]
            if self.password_edit.text():
                args.append(self.password_edit.text())
        args += ["+workshop_download_item", self.app_id_edit.text().strip(), self.workshop_id_edit.text().strip(), "+quit"]
        return args

    def _get_masked_args_str(self, args):
        masked = list(args)
        for i in range(len(masked)):
            if masked[i] == "+login" and i + 2 < len(masked):
                if masked[i+1] != "anonymous": masked[i+2] = "********"
        return " ".join(masked)

    def validate_inputs(self):
        if not os.path.isfile(self.steamcmd_path_edit.text().strip()):
            QMessageBox.warning(self, self.tr("エラー"), self.tr("SteamCMD.exeが見つかりません。"))
            return False
        if not self.app_id_edit.text().strip().isdigit() or not self.workshop_id_edit.text().strip().isdigit():
            QMessageBox.warning(self, self.tr("エラー"), self.tr("IDは数字で入力してください。"))
            return False
        return True

    def stop_process(self):
        if self.process.state() != QProcess.NotRunning:
            self.append_log("\n" + self.tr("=== 停止要求を送信しました ==="))
            self.process.kill()

    def send_command(self):
        cmd = self.cmd_input_edit.text()
        if cmd and self.process.state() != QProcess.NotRunning:
            self.append_log(f"> {cmd}")
            self.process.write((cmd + "\n").encode("utf-8"))
            self.cmd_input_edit.clear()
        elif cmd:
            self.append_log(self.tr("エラー: SteamCMDが実行されていません。"))

    def read_stdout(self):
        txt = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if txt: self.append_log(txt.rstrip())

    def read_stderr(self):
        txt = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        if txt: self.append_log(txt.rstrip())

    def on_process_started(self): self.append_log(self.tr("SteamCMDを起動しました。"))

    def on_process_finished(self, code, status):
        self.append_log("\n" + self.tr("=== SteamCMD 終了 (コード: {0}) ===").format(code))
        self.status_label.setText(self.tr("完了"))
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def on_process_error(self, err):
        self.append_log("\n" + self.tr("=== エラー: {0} ===").format(err))
        self.status_label.setText(self.tr("エラー"))
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def open_output_dir(self):
        path = self.output_dir_edit.text().strip()
        if os.path.isdir(path): QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else: QMessageBox.warning(self, self.tr("エラー"), self.tr("保存先フォルダが存在しません。"))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SteamCMDGui()
    window.show()
    sys.exit(app.exec())