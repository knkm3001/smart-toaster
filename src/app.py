import sys
import time
import copy
import random
import atexit
import signal
import redis
import multiprocessing
from typing import Final
from dataclasses import dataclass

from flask import Flask, render_template, jsonify, request

# import read_temp_max6755 as max6755
from read_temp import read_temp
from ssr_control import gpio_control, gpio_creanup
from pid import run_pid_process
from api_utils import generate_interp_profile

# PID制御器のパラメータとサンプリング時間のデフォルト値
KP:Final[float] = 10.0  # 比例
KI:Final[float] = 0.05  # 積分
KD:Final[float] = 18.0  # 微分
DT:Final[float] = 1.0   # サンプリング時間[sec]

cleanup_done = False
process = None
recipe:dict = {} 

manager = multiprocessing.Manager() # プロセス間でデータを共有のため、共有オブジェクトを作成
status = manager.Value('s', 'not running')
# status:
# - not running: まだPIDプロセスが起動していない
# - running: PIDプロセスが起動中
# - finished: PIDプロセス正常終了
# - killed: PIDプロセス強制終了

@dataclass
class PidParam:
    kp: float
    ki: float
    kd: float
    dt: float

# redis用client
client = redis.Redis(host='redis', port=6379, db=0)

app = Flask(__name__)

@app.route('/')
def index():
    """
    webUI用エンドポイント
    """
    return render_template('index.html')


@app.route('/get_default_param')
def get_default_param():
    """
    デフォルトのパラメータを取得するためのエンドポイント
    """
    return jsonify(
        default_pid_param = {
            "kp": KP,
            "ki": KI,
            "kd": KD,
            "dt": DT
        }
        )


@app.route('/get_current_status')
def get_current_status():
    """
    現在のステータスを取得するためのエンドポイント
    """
    return jsonify(
        current_temp = read_temp(),
        timestamp = int(time.time()),
        process_status = status.value,
        # TODO redis 読む
        current_pid_proc_status = None
        ),200


@app.route('/kill_process')
def kill_process():
    """
    PID制御プロセスを停止するためのエンドポイント
    """
    global process, status
    gpio_control(power=False) # とにかくpowerはoff

    if process is None or not process.is_alive():
        if status.value == 'finished':
            return jsonify({'message': 'Process is already finished'}), 200
        elif status.value == 'killed':
            return jsonify({'message': 'Process is already killed'}), 200
        else:
            return jsonify({'message': 'Process is not running'}), 200
    else:
        process.terminate()
        process.join() # 子プロセスが完全にkillされることを待つ
        status.value = 'killed'
        return jsonify({'message': 'Task killed'}), 200


@app.route('/run_process',methods=["POST"])
def run_process():
    """
    PIDプロセスを起動するためのエンドポイント
    """
    global process, status

    # 与えられたプロファイルに従ってPID制御を行う
    if not request.method == 'POST':
        return jsonify({'error': 'POST required'}), 400
    elif process is not None and process.is_alive():
        return jsonify({'error': 'process is already running'}), 400
    else:
        payload = request.get_json()

        if payload is None:
            # JSON データが存在しない場合、400 ステータスコードを返す
            return jsonify({'error': 'No payload provided'}), 400
        elif not payload.get("profile") or not payload.get("pid_param"):
            return jsonify({'error': 'invalid payload provided'}), 400
        else:
            recipe = copy.deepcopy(payload)
            recipe["profile"] = generate_interp_profile(payload["profile"])
            if not recipe["profile"]:
                return jsonify({'message': 'invalid profile'}), 400
            
            # PID制御プロセスを非同期で実行
            process = multiprocessing.Process(target=run_pid_process, args=(status,recipe))
            process.start()
            status.value = 'running'
            print('process start!! pid: ',process.pid)
            return jsonify({'message': 'process started'}), 200


@app.route('/status_clear')
def status_clear():
    """
    redisに記録されているPIDプロセスのステータスを初期化する
    """
    global status

    if process is None or not process.is_alive():
        client.flushdb() # redis clear
        status.value  = 'not running'
        return jsonify({'message': 'status is cleared'}), 200
    else:
        return jsonify({'message': 'process is alive'}), 400


@app.route('/get_pid_proc_status', methods=['POST'])
def get_log():
    """
    redisに記録されているPIDプロセスのステータスをすべて取得する
    """
    return 200


@app.route('/set_profile', methods=['POST'])
def set_profile():
    """
    既存のプロファイルを読み込む
    """
    return 200
    # プロファイルデータを読み込む
    payload_profile = request.get_json()
    print('payload_profile',payload_profile)
    if payload_profile is None:
        # JSON データが存在しない場合、400 ステータスコードを返す
        return jsonify({'error': 'No profile provided'}), 400
    elif status.value  != 'not running':
        return jsonify({'error': 'PID process is already runnning'}), 400
    else:
        interp_profile = generate_interp_profile(payload_profile)
        return jsonify({'message': 'received profile'}), 200


def cleanup():
    global cleanup_done
    if not cleanup_done:
        cleanup_done = True
        print("Cleaning up resources...")
        gpio_control(power=False)
        gpio_creanup()
    print('clean up done')


def exit_handler(signal, frame):
    print("Ctrl+C pressed. Exiting...")
    cleanup()
    sys.exit(0)


signal.signal(signal.SIGINT, exit_handler) # Ctrl+C (デバッグモードだとプロセスが二つあるから２回実行される)
#atexit.register(cleanup) # 通常修了時

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

        
