import sys
import time
import random
import atexit
import signal
import multiprocessing

from flask import Flask, render_template, jsonify, request

from read_temp import read_temp
from pid import run_pid_process, ssr_control, gpio_creanup, generate_interp_data

cleanup_done = False
process = None
gpio_pin = 14

manager = multiprocessing.Manager() # プロセス間でデータを共有のため、共有オブジェクトを作成
status = manager.Value('s', 'not running')

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/get_status')
def get_status():
    dummy = False # TODO for dev
    temperature = round(random.uniform(20, 30), 2) if dummy else read_temp()
    return jsonify(
        temperature = temperature,
        timestamp = int(time.time()),
        process_status = status.value
        )


@app.route('/cancel_process')
def cancel_process():
    global process, status
    ssr_control(power=False) # とにかくpowerはoff

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


@app.route('/status_clear')
def status_clear():
    global status
    if process is None or not process.is_alive():
        status.value  = 'not running'
        return jsonify({'message': 'status is cleared'}), 200
    else:
        return jsonify({'message': 'process is alive'}), 400


@app.route('/get_profile', methods=['POST'])
def get_profile():
    # プロファイルデータ
    payload_profile = request.get_json()
    print('payload_profile',payload_profile)
    if payload_profile is None:
        # JSON データが存在しない場合、400 ステータスコードを返す
        return jsonify({'error': 'No profile provided'}), 400
    else:
        profile = generate_interp_data(payload_profile)
        return jsonify(profile), 200


@app.route('/run_process',methods=["POST"])
def run_process():
    global process, status

    # 与えられたプロファイルに従ってトースターを操作する
    if not request.method == 'POST':
        return jsonify({'error': 'POST required'}), 400
    elif process is not None and process.is_alive():
        return jsonify({'error': 'process is already running'}), 400
    else:
        payload_profile = request.get_json()
        print('payload_profile',payload_profile)

        if payload_profile is None:
            # JSON データが存在しない場合、400 ステータスコードを返す
            return jsonify({'error': 'No profile provided'}), 400
        else:
            profile = generate_interp_data(payload_profile)
            if not profile:
                return jsonify({'message': 'invalid profile'}), 400
            
            print('profile:',profile)
            print('process start')
            process = multiprocessing.Process(target=run_pid_process, args=(status,profile))
            process.start()
            status.value = 'running'
            return jsonify({'message': 'process started'}), 200


def cleanup():
    global cleanup_done
    if not cleanup_done:
        cleanup_done = True
        print("Cleaning up resources...")
        ssr_control(power=False)
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

        
