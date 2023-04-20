from flask import Flask, render_template, jsonify, request
import random
import time
import sys
import atexit
import signal
import concurrent.futures
import RPi.GPIO as GPIO

from read_temp import read_temp
from pid import do_pid_process, ssr_control

GPIO.setmode(GPIO.BCM)
GPIO.setup(14,GPIO.OUT)
cleanup_done = False
print(type(GPIO),id(GPIO))

app = Flask(__name__)
app.is_running = False
app.future = None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/get_status')
def get_status():
    # ここで、既存のPythonプログラムを使って温度センサーからデータを取得します。
    # 仮のデータを返すために、ランダムな温度を生成します。
    dummy = False
    temperature = round(random.uniform(20, 30), 2) if dummy else read_temp()
    return jsonify(
        temperature=temperature,
        timestamp=int(time.time()),
        is_running=app.is_running
        )


@app.route('/cancel_process')
def cancel_process():
    print('stop!!!!!!!')
    ssr_control(GPIO,power=False)
    app.is_running = False
    app.future.cancel()
    return jsonify({'message': 'process stoped'}), 200


@app.route('/run_process',methods=["POST"])
def exec_profile():
    # 与えられたプロファイルに従ってトースターを操作する
    if not request.method == 'POST':
        return jsonify({'error': 'POST required'}), 400
    elif app.is_running:
        return jsonify({'error': 'process is running'}), 400
    else:
        print('request',request)
        data = request.get_json()
        print(data)

        if data is None:
            # JSON データが存在しない場合、400 ステータスコードを返す
            return jsonify({'error': 'No data provided'}), 400
        else:
            app.is_running = True
            print('process start')
            # 非同期の別プロセスでヒーターをPID制御
            with concurrent.futures.ThreadPoolExecutor() as executor:
                app.future = executor.submit(do_pid_process, data,GPIO)

            return jsonify({'message': 'Data received successfully'}), 200


def cleanup():
    global cleanup_done
    if not cleanup_done:
        print("Cleaning up resources...")
        ssr_control(GPIO,power=False)
        GPIO.cleanup()
        cleanup_done = True

def exit_handler(signal, frame):
    print("Ctrl+C pressed. Exiting...")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, exit_handler) # Ctrl+c時
atexit.register(cleanup) # 通常修了時


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

        
