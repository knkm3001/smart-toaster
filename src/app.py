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

manager = multiprocessing.Manager() # プロセス間でデータを共有のため、共有オブジェクトを作成
process_status = manager.Value('s', 'not running')
# process_status:
# - not running: まだPIDプロセスが起動していない
# - running: PIDプロセスが起動中
# - finished: PIDプロセス正常終了
# - killed: PIDプロセス強制終了
# - error: 何らかの理由でエラー

# redis用client
client = redis.Redis(host='redis', port=6379, db=0)
client.set('process_status','not running')

app = Flask(__name__)

@dataclass
class PidParam:
    kp: float
    ki: float
    kd: float
    dt: float



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


@app.route('/get_status')
def get_current_status():
    """
    現在のステータスを取得するためのエンドポイント
    """
    min_key = request.args.get('minKey',None)
    with_profile = request.args.get('withProfile',False)
    status = {}
    
    redis_keys = client.keys()
    for key in redis_keys:
        str_key = key.decode('utf-8')
        if str_key == "profile" and not with_profile:
            continue
        if min_key is not None and int(str_key) <= int(min_key):
            continue
        val = client.get(key)
        str_val = val.decode('utf-8') if val is not None else None
        status[str_key] = str_val

    return jsonify(
        current_temp = read_temp(),
        timestamp = int(time.time()),
        status = status
        ),200


@app.route('/kill_process')
def kill_process():
    """
    PID制御プロセスを停止するためのエンドポイント
    """
    global process, process_status
    gpio_control(power=False) # とにかくpowerはoff

    process_status = client.get('process_status').decode('utf-8')

    if process is None or not process.is_alive():
        if process_status== 'finished':
            return jsonify({'message': 'Process is already finished'}), 200
        elif process_status== 'killed':
            return jsonify({'message': 'Process is already killed'}), 200
        else:
            return jsonify({'message': 'Process is not running'}), 200
    else:
        process.terminate()
        process.join() # 子プロセスが完全にkillされることを待つ
        client.set('process_status','killed')
        return jsonify({'message': 'Task killed'}), 200


@app.route('/run_process',methods=["POST"])
def run_process():
    """
    PIDプロセスを起動するためのエンドポイント
    """
    global process, process_status

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
            pid_param = payload["pid_param"]
            interp_profile = generate_interp_profile(payload["profile"])
            if not interp_profile:
                return jsonify({'message': 'invalid profile'}), 400
            
            # PID制御プロセスを非同期で実行
            process = multiprocessing.Process(target=run_pid_process, args=(interp_profile,pid_param))
            process.start()
            client.set('process_status','running')
            print('process start!! pid: ',process.pid)
            return jsonify({'message': 'process started'}), 200


@app.route('/status_clear')
def status_clear():
    """
    redisに記録されているPIDプロセスのステータスを初期化する
    """
    global process_status

    if process is None or not process.is_alive():
        client.flushdb() # redis clear
        client.set('process_status','not running')
        return jsonify({'message': 'process_status is cleared'}), 200
    else:
        return jsonify({'message': 'process is alive'}), 400


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

        
