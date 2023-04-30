import time
import numpy as np
import RPi.GPIO as GPIO
from scipy.interpolate import interp1d
from typing import Final
from collections import deque
from datetime import datetime

from read_temp import read_temp

# PID制御器のパラメータとサンプリング時間
kp = 10.0  # 比例
ki = 0.05  # 積分
kd = 8.0 # 微分
dt = 1.0  # サンプリング時間[sec]


MV_THRESHOLD:Final[float] = 1000.0 
TEMP_THRESHOLD:Final[int] = 1000.0 #[℃] PIDが働く範囲

GPIO_PIN:Final[int] = 14
GPIO.setmode(GPIO.BCM)
GPIO.setup(GPIO_PIN,GPIO.OUT)


def gpio_creanup():
    GPIO.cleanup()


def ssr_control(power:bool):
    if power:
        GPIO.output(GPIO_PIN,GPIO.HIGH)
    else:
        GPIO.output(GPIO_PIN,GPIO.LOW)


def run_pid_process(status,profile):
    try:
        
        pid = PIDController(kp, ki, kd, dt)
        current_time = 0
        for data in profile:
            error = data['temp'] - read_temp()

            mv = pid.update(error) # PID制御器の更新
            pot = round(dt*mv/MV_THRESHOLD,2) # [sec]

            print(f"Time: {data['time']}, Target temp: {round(data['temp'],2)}, Current temp: {read_temp()}, mv: {round(mv,2)}, toaster Ton: {pot} [sec]")
            if pot > 0:
                pot = pot if pot > 0.01 else 0.01
                ssr_control(power=True)
                time.sleep(pot) # pwm on
                if pot < dt: 
                    ssr_control(power=False)
                    time.sleep(dt-pot) # pwm off
            else:
                ssr_control(power=False)
                time.sleep(dt)
            current_time += dt
        else:
            ssr_control(power=False)
            status.value = 'finished'
    except Exception as e:
        ssr_control(power=False)
        print('error!:',str(e))
        status.value = 'error'


def generate_interp_data(data):
    """
    与えられたデータを線形補完する

    Args:
        data (list): [{'x':int,'y':int}...] xが時間、yが温度
    Returns:
        list: [{'time':int,'temp':int}...] xが時間、yが温度
    """

    x_new = np.array([])
    y_new = np.array([])

    is_invalid_data = False
    ex_coord = None
    for coord in data:
        if ex_coord is None:
            if coord['x'] != 0:
                is_invalid_data = True
                break
            else:
                ex_coord = coord
                continue
        else:
            if coord['x'] < ex_coord['x']:
                is_invalid_data = True
                break
            # 線形補間を行う一時関数を作成
            f = interp1d([ex_coord['x'],coord['x']], [ex_coord['y'],coord['y']], kind='linear')
            x_generated = np.arange(ex_coord['x'], coord['x'])
            x_new = np.concatenate([x_new, x_generated]) 
            y_new = np.concatenate([y_new, f(x_generated)])
            ex_coord = coord
        
    if is_invalid_data:
        return []
    else:
        return [{'time':x,'temp':y} for x,y in zip(x_new,y_new)]


class PIDController:
    """
    PID制御器クラス
    """
    def __init__(self, kp, ki, kd, dt):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.dt = dt
        self.ex_mv = 0.0
        self.ex_err = 0.0
        self.ex2_err = 0.0
        
        self.is_windup = False
        self.data_file = 'data_'+datetime.now().strftime("%Y%m%d_%H%M") + '.txt'

        self.use_integral_limit = False
        if self.use_integral_limit:
            self.integral_sec = 180
            self.integral = BoundedQueue(self.integral_sec) # arg [sec]分の変数を誤差量としてため込む
        else:
            self.integral = 0.0



    def reset_param(self):
        self.ex_mv = 0.0
        self.ex_err = 0.0
        self.ex2_err = 0.0
        self.is_windup = False
        if self.use_integral_limit:
            self.integral = BoundedQueue(self.integral_sec)
        else:
            self.integral = 0.0
        

    def update(self, err:float, ftype:str='default') -> float:
        """
        サンプリング方式のPID制御
        """
        if ftype=='sampling':
            current_mv = self.kp * (err - self.ex_err) + self.ki * err + self.kd * ((err - self.ex_err)-(self.ex_err - self.ex2_err))
            output = current_mv + self.ex_mv
            self.ex_mv = current_mv
            self.ex_err2 = self.ex_err
            self.ex_err = err
        else:
            vp = self.kp * err
            
            err_s = (err + self.ex_err)*self.dt/2 # 台形近似
            #err_s = err * self.dt # 柵近似

            if self.use_integral_limit:
                self.integral.put(err_s) 
                vi = self.ki * sum(self.integral.get_values())
                integral = sum(self.integral.get_values())
            else:
                if not self.is_windup:
                    self.integral += err_s
                vi = self.ki * self.integral
                integral = self.integral

            vd = self.kd * (err - self.ex_err) / self.dt
            self.ex_err = err
            
            output = vp + vi + vd

            if output > MV_THRESHOLD:
                output = MV_THRESHOLD
                self.is_windup = True
            elif output < 0:
                self.is_windup = True
                output = 0
            else:
                self.is_windup = False

            with open(self.data_file, 'a') as file:
                 data = f'mv:{output},vp:{vp},vi:{vi},vd:{vd},integral:{integral}'
                 file.write(data + '\n')
            print('mv',output,'vp',vp,'vi',vi,'vd',vd,'integral',integral)
            return output
        

class BoundedQueue:
    """
    制限付きキュー
    """
    def __init__(self, max_size):
        self.queue = deque(maxlen=max_size)

    def put(self, item):
        self.queue.append(item)

    def get(self):
        if len(self.queue) > 0:
            return self.queue.popleft()
        else:
            return None

    def size(self):
        return len(self.queue)

    def is_full(self):
        return len(self.queue) == self.queue.maxlen

    def is_empty(self):
        return len(self.queue) == 0

    def get_values(self):
        return list(self.queue)