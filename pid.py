import time
from typing import Final
from collections import deque
from datetime import datetime

import numpy as np
import RPi.GPIO as GPIO
from scipy.interpolate import interp1d

import read_temp_max6755 as max6755
from read_temp import read_temp

# PID制御器のパラメータとサンプリング時間
kp:Final[float] = 10.0  # 比例
ki:Final[float] = 0.05  # 積分
kd:Final[float] = 20.0 # 微分
dt:Final[float] = 1.0  # サンプリング時間[sec]

MV_THRESHOLD:Final[float] = 1000.0 # 操作量の閾値

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
        data_file = 'data_'+datetime.now().strftime("%Y%m%d_%H%M") + '.txt'

        for data in profile:
            error = data['temp'] - max6755.read_temp()
            pid.update(error) # PID制御器の更新
            param = pid.get_current_pid_param()
            for key,val in param.items():
                param[key] = round(val,2)
            print(param)
            pot = round(dt*param['mv']/MV_THRESHOLD,2) # power on time [sec]

            current_data = f"Time: {data['time']}, Target temp: {data['temp']}, Current temp: {max6755.read_temp()}, toaster Ton: {pot} [sec], mv:{param['mv']}, vp:{param['vp']}, vi:{param['vi']}, vd:{param['vd']}, integral:{param['integral']}"
            with open(data_file, 'a') as file:
                 file.write(current_data + '\n')
            print(current_data)

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
    except KeyboardInterrupt:#Exception as e:
        ssr_control(power=False)
        print('error!:',str(e))
        status.value = 'error:' + str(e)


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
        return [{'time':x,'temp':round(y,2)} for x,y in zip(x_new,y_new)]


class PIDController:
    """
    PID制御器クラス
    """
    def __init__(self, kp, ki, kd, dt):
        # 定数
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.dt = dt
        
        # 変数
        self.mv = 0
        self.vp = 0
        self.vi = 0
        self.vd = 0
        self.ex_mv = 0.0
        self.ex_err = 0.0
        self.ex2_err = 0.0

        self.is_windup = False

        self.use_integral_limit = False # エラーの積分値に範囲を与える
        if self.use_integral_limit:
            self.integral_sec = 180 # [sec]
            self.integral = BoundedQueue(self.integral_sec) # arg [sec]分の変数を誤差量としてため込む
        else:
            self.integral = 0.0


    def reset_param(self):
        self.mv = 0
        self.vp = 0
        self.vi = 0
        self.vd = 0
        self.ex_mv = 0.0
        self.ex_err = 0.0
        self.ex2_err = 0.0
        self.is_windup = False
        if self.use_integral_limit:
            self.integral_que = BoundedQueue(self.integral_sec)
        self.integral = 0.0
    
    
    def get_current_pid_param(self):
        return {'mv':self.mv,'vp':self.vp,'vi':self.vi,'vd':self.vd,'integral':self.integral}


    def update(self, err:float, ftype:str='default') -> float:
        """
        パラメータ更新
        """
        if ftype=='sampling':
            self.vp = self.kp * (err - self.ex_err)
            self.vi = self.ki * err
            self.vd = self.kd * ((err - self.ex_err)-(self.ex_err - self.ex2_err))
            current_mv = self.vp + self.vi + self.vd 
            self.mv = current_mv + self.ex_mv
            self.ex_mv = current_mv
            self.ex_err2 = self.ex_err
            self.ex_err = err
        else:
            self.vp = self.kp * err
            
            err_s = (err + self.ex_err)*self.dt/2 # 台形近似
            #err_s = err * self.dt # 柵近似

            if self.use_integral_limit:
                self.integral_que.put(err_s) 
                self.vi = self.ki * sum(self.integral_que.get_values())
                self.integral = sum(self.integral_que.get_values())
            else:
                if not self.is_windup:
                    self.integral += err_s
                self.vi = self.ki * self.integral

            self.vd = self.kd * (err - self.ex_err) / self.dt
            self.ex_err = err
            
            mv = self.vp + self.vi + self.vd

            if mv > MV_THRESHOLD:
                self.is_windup = True
                self.mv = MV_THRESHOLD
            elif mv < 0:
                self.is_windup = True
                self.mv = 0
            else:
                self.is_windup = False
                self.mv = mv
        

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