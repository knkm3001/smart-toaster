import sys
import time
import json
import random
import atexit
import signal
import redis
import multiprocessing
from typing import Final

from flask import Flask, render_template, jsonify, request

# import read_temp_max6755 as max6755
from read_temp import read_temp
from ssr_control import gpio_control, gpio_creanup
from pid import pid_process
from api_utils import generate_interp_profile
from redis_client import redis_client

# PID制御器のパラメータとサンプリング時間のデフォルト値
KP:Final[float] = 10.0  # 比例
KI:Final[float] = 0.1   # 積分
KD:Final[float] = 18.0  # 微分
DT:Final[float] = 1.0   # サンプリング時間[sec]

cleanup_done = False
process = None

default_pid_param = {"kp":KP,"ki":KI,"kd":KD,"dt":DT}

# redis用client
client = redis_client()
client.flushdb() # redis clear
client.set('pid_process_status','not running')
client.set('pid_param',json.dumps(default_pid_param))

app = Flask(__name__)





@app.route('/')
def index():
    """
    webUI用エンドポイント
    """
    return render_template('index.html')


@app.route('/get_status')
def get_current_status():
    """
    現在のステータスを取得するためのエンドポイント

    Params:
        minKey (int): redisで取得する値のうち、 minKey < key となるデータを取得する。minKeyがなければすべてのデータを返す。
        isInit (bool): 初期データを含めるかどうか(option)

    Returns:
        dict: 現在のステータス
            - current_temp (dict): 現在の温度
            - timestamp (float): 現在のunix time
            - pid_process_status (str): PID制御プロセスのステータス
            - status_data (list): 各実行時間ごとのデータ
            - pid_param (dict): pidパラメータ(option)
            - profile (list): profile(option)
    """

    # TODO バリデータ
    min_key = request.args.get('minKey',0)
    if min_key != 0 and not min_key.isdigit():
        return jsonify({'error': 'invalid parametor provided'}), 400
    min_key = int(min_key)

    is_init = request.args.get('isInit',False)

    pid_process_status_val = client.get('pid_process_status')
    pid_process_status = pid_process_status_val.decode('utf-8')

    if is_init:
        pid_param_val = client.get('pid_param')
        pid_param = json.loads(pid_param_val.decode('utf-8'))

        profile_val = client.get('profile')
        profile = json.loads(profile_val.decode('utf-8')) if profile_val else []

        if client.exists('status_data'):
            status_data_val = client.lrange('status_data', 0, -1)
            status_data = [json.loads(value.decode('utf-8')) for value in status_data_val]
        else:
            status_data = []

        return jsonify(
            current_temp = read_temp(),
            current_timestamp = time.time(),
            pid_process_status = pid_process_status,
            pid_param = pid_param,
            status_data = status_data,
            profile = profile
            ),200
    else:
        status_data_val = client.lrange('status_data', min_key, -1)
        status_data = [json.loads(value.decode('utf-8')) for value in status_data_val]
        return jsonify(
            current_temp = read_temp(),
            current_timestamp = time.time(),
            pid_process_status = pid_process_status,
            status_data = status_data
            ),200


@app.route('/get_chart_data')
def get_chart_data():
    """
    chartデータを全部取得

    Returns:
        recipe (bool): 使用したオリジナルのプロファイルとPIDパラメータを取得する
            - pid_param (dict):
            - profile (list): 
        interp_profile (bool): 線形補間したプロファイルを取得する
        status_data (list): データ
    """
    recipe = {}
    values = client.mget(['pid_param','profile', 'interp_profile'])
    decoded_values = [value.decode('utf-8') for value in values]
    recipe['pid_param'] = json.loads(decoded_values[0])
    recipe['profile'] = json.loads(decoded_values[1])
    interp_profile = json.loads(decoded_values[2])
    
    status_data_val = client.lrange('status_data', 0, -1)
    status_data = [json.loads(value.decode('utf-8')) for value in status_data_val]

    return jsonify(
        recipe = recipe,
        interp_profile = interp_profile,
        status_data = status_data
        ),200


@app.route('/run_process',methods=["POST"])
def run_process():
    """
    PIDプロセスを起動するためのエンドポイント
    """
    global process

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
        elif not payload.get("profile"):
            return jsonify({'error': 'invalid payload provided'}), 400
        else:

            # pid param取得
            if payload.get("pid_param"):
                try:
                    for v in payload["pid_param"].values():
                        isinstance(float(v), float)
                except Exception as e:
                    return jsonify({'error': 'invalid prid_param provided' + str(e)}), 400 

                pid_param = payload["pid_param"]
            else:
                pid_param = default_pid_param

            # 線形補間 TODO バリデータ
            interp_profile = generate_interp_profile(payload["profile"])
            if not interp_profile:
                return jsonify({'message': 'invalid profile'}), 400

            kv_pairs = {
                'profile': json.dumps(payload["profile"]),
                'interp_profile': json.dumps(interp_profile),
                'pid_param': json.dumps(pid_param),
            }
            client.mset(kv_pairs)

            # PID制御プロセスを非同期で実行
            process = multiprocessing.Process(target=pid_process)
            process.start()
            print('process start!! pid: ',process.pid)
            return jsonify({'message': 'process started'}), 200


@app.route('/kill_process')
def kill_process():
    """
    PID制御プロセスを停止するためのエンドポイント
    """
    global process
    gpio_control(power=False) # とにかくpowerはoff

    pid_process_status = client.get('pid_process_status').decode('utf-8')

    if process is None or not process.is_alive():
        if pid_process_status== 'finished':
            return jsonify({'message': 'Process is already finished'}), 200
        elif pid_process_status== 'killed':
            return jsonify({'message': 'Process is already killed'}), 200
        else:
            return jsonify({'message': 'Process is not running'}), 200
    else:
        process.terminate()
        process.join() # 子プロセスが完全にkillされることを待つ
        client.set('pid_process_status','killed')
        return jsonify({'message': 'Task killed'}), 200


@app.route('/status_clear')
def status_clear():
    """
    redisに記録されているPIDプロセスのステータスを初期化する
    """

    if process is None or not process.is_alive():
        client.mset({
            'pid_process_status': 'not running',
            'pid_param': json.dumps(default_pid_param)
        })
        keys_to_delete = ['profile', 'interp_profile', 'status_data']
        client.delete(*keys_to_delete)
        return jsonify({'message': 'pid_process_status is cleared'}), 200
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

        
