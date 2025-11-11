import subprocess
import sys
from pathlib import Path

# --- 設定 ---
BASE_DIR = Path('/home/ubuntu/cur/isep/clause-viewer')
SCRIPTS = [
    "setup_database.py",
    "import_csv_to_sqlite.py",
    "export_sqlite_to_json.py",
    "export_split_json.py"
]

def run_script(script_name):
    """指定されたPythonスクリプトを実行する"""
    script_path = BASE_DIR / script_name
    print("\n" + "=" * 60)
    print(f"実行中: {script_name}")
    print("=" * 60)
    
    try:
        # subprocessを使って別プロセスとして実行
        # これにより、各スクリプトが独立した環境で動作し、変数の競合などを防ぐ
        process = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            check=True, # エラーが発生したら例外を発生させる
            cwd=BASE_DIR
        )
        # 標準出力を表示
        print(process.stdout)
        if process.stderr:
            print("--- 標準エラー出力 ---")
            print(process.stderr)
        
        return True

    except FileNotFoundError:
        print(f"エラー: スクリプトが見つかりません - {script_path}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"エラー: {script_name} の実行中にエラーが発生しました。")
        print(f"リターンコード: {e.returncode}")
        print("\n--- 標準出力 ---")
        print(e.stdout)
        print("\n--- 標準エラー出力 ---")
        print(e.stderr)
        return False
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        return False


def main():
    """
    データ更新プロセス全体を管理する統合スクリプト
    """
    print("############################################################")
    print("############ Clause Viewer データ更新プロセス開始 ############")
    print("############################################################")

    # 順番にスクリプトを実行
    for script in SCRIPTS:
        if not run_script(script):
            print(f"\nプロセスが '{script}' で停止しました。")
            break
    else: # ループが正常に完了した場合
        print("\n############################################################")
        print("############ 全てのプロセスが正常に完了しました ############")
        print("############ data-integrated.json を更新しました ############")
        print("############################################################")


if __name__ == '__main__':
    main()
