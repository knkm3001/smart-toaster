import time
import numpy as np
import RPi.GPIO as GPIO
from scipy.interpolate import interp1d
from typing import Final

from read_temp import read_temp

# PID制御器のパラメータとサンプリング時間
kp = 1.0
ki = 0.1
kd = 0.05
dt = 1.0

MV_THRESHOLD:Final[float] = 0.5
TEMP_THRESHOLD:Final[int] = 40

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
    pid = PIDController(kp, ki, kd, dt)

    profile = generate_interp_data(profile)
    print('profile:',profile)
    for data in profile:
        print('current target',data)
        
        error = data['temp'] - read_temp()
        
        # 誤差量が閾値内のときだけPIDする
        if error > TEMP_THRESHOLD:
            ssr_control(power=True)
            pid.param_reset()
        elif error < -1*TEMP_THRESHOLD:
            ssr_control(power=False)
            pid.param_reset()
        else:
            mv = pid.update(error) # PID制御器の更新
            power = True if mv >= MV_THRESHOLD else False
            ssr_control(power)
    
        print(f"Time: {data['time']}, Target temp: {data['temp']}, Current temp: {read_temp()}, mv: {mv}, toaster power: {power}")
    
        time.sleep(dt) # サンプリング時間だけ待機
    else:
        ssr_control(power=False)
        status.value = 'finished'


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

    ex_coord = None
    for coord in data:
        if ex_coord is None:
            ex_coord = coord
            continue
        else:
            # 線形補間を行う一時関数を作成
            f = interp1d([ex_coord['x'],coord['x']], [ex_coord['y'],coord['y']], kind='linear')
            x_generated = np.arange(ex_coord['x'], coord['x'])
            x_new = np.concatenate([x_new, x_generated]) 
            y_new = np.concatenate([y_new, f(x_generated)])
            ex_coord = coord

    return [{'time':x,'temp':y} for x,y in zip(x_new,y_new)]


# PID制御器クラス
class PIDController:
    def __init__(self, kp, ki, kd, dt):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.dt = dt
        self.integral = 0.0
        self.prev_error = 0.0
    
    def param_reset(self) -> None:
        self.integral = 0.0
        self.prev_error = 0.0

    def update(self, error:float) -> float:
        self.integral += error * self.dt
        derivative = (error - self.prev_error) / self.dt
        self.prev_error = error
        output = self.kp * error + self.ki * self.integral + self.kd * derivative
        return output
