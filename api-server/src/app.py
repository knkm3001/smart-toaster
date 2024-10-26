import sys
import time
import json
import os
import signal
import multiprocessing
from typing import Final

from flask import Flask, render_template, jsonify, request
from data_models import PIDParams, StatusData, Recipe

# import read_temp_max6755 as max6755
from read_temp import read_temp
from ssr_control import gpio_control, gpio_creanup
from pid import pid_process
from api_utils import generate_interp_profile
from redis_client import redis_client


REDIS_HOSTS:Final[str] = os.environ['REDIS_HOSTS']
REDIS_PORT:Final[str] = os.environ['REDIS_PORT']

# PID制御器のパラメータとサンプリング時間のデフォルト値
pid_params = PIDParams()

cleanup_done = False
process = None

default_pid_param = {
    "kp": pid_params.kp,
    "ki": pid_params.ki,
    "kd": pid_params.kd,
    "dt": pid_params.dt,
    "mv_threshold": pid_params.dtmv_threshold
    }

# redis用client
client = redis_client(REDIS_HOSTS,REDIS_PORT)
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

    try:
        min_key = int(request.args.get('minKey', 0))
        if min_key < 0:
            raise ValueError
    except ValueError:
        return jsonify({'error': 'invalid parameter provided'}), 400

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
            status_data = status_data,
            pid_param = pid_param,
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

    Params:
        None

    Returns:
        recipe (dict): 使用したオリジナルのプロファイルとPIDパラメータを取得する
            - pid_param (dict):
            - profile (list): 
        interp_profile (bool): 線形補間したプロファイルを取得する
        status_data (status): データ
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
    レシピデータをPOSTし、PIDプロセスを起動するためのエンドポイント

    Payload:
        profile (dict): プロセスのプロファイル設定。
        pid_param (dict): プロセスを起動するために必要なパラメータ。Optional


    Returns:
        dict: 実行結果
            - message (str): 実行結果を伝えるメッセージ
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

            # バリデートチェック
            try:
                recipe = Recipe(**payload)
                pid_param = recipe.pid_param.dict() if recipe.pid_param else default_pid_param
            except Exception as e:
                return jsonify({'error': 'invalid prid_param provided' + str(e)}), 400 

            # 線形補間
            try:
                recipe_profile_points = [point.dict() for point in recipe.profile]
                interp_profile = generate_interp_profile(recipe_profile_points)
            except Exception as e:
                return jsonify({'error': 'invalid profile' + str(e)}), 400 

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

    Params:
        None
        
    Returns:
        dict: 実行結果
            - message (str): 実行結果を伝えるメッセージ
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

    Params:
        None
        
    Returns:
        dict: 実行結果
            - message (str): 実行結果を伝えるメッセージ
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
#atexit.register(cleanup) # 通常終了時

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

        
