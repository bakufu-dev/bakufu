"""Bootstrap Stage 用の設定ヘルパ群（DATA_DIR 解決など）。

これらのモジュールは OS レベルの状態をインフラストラクチャ層の
他の部分へ橋渡しする。SQLite エンジン準備前（Bootstrap Stage 1）に
動作するため、persistence パッケージの *外側* に位置する。
"""
