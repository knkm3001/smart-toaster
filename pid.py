import time
import numpy as np
from scipy.interpolate import interp1d

from read_temp import read_temp

# PID制御器のパラメータとサンプリング時間
kp = 1.0
ki = 0.1
kd = 0.05
dt = 1.0
threshold = 0.5

def ssr_control(GPIO,power:bool):
    gpio_status = GPIO.HIGH if power else GPIO.LOW
    GPIO.output(14,gpio_status)


def do_pid_process(profile,GPIO):

    pid = PIDController(kp, ki, kd, dt)

    profile = generate_interp_data(profile)
    print('profile:',profile)
    for data in profile:
        print('current target',data)
        
        error = data['temp'] - read_temp()

        power = False
        if error > 40:
            power = True
            ssr_control(GPIO,power=power)
            pid.param_reset()
        elif error < -40:
            ssr_control(GPIO,power=False)
            pid.param_reset()
        else:
            # -40 < temp < 40 のときpid
            # PID制御器の更新
            control_signal = pid.update(error)
            power = True if control_signal >= threshold else False
            ssr_control(GPIO,power=power)
    
        # 結果の表示
        print(f"Time: {data['time']}, Target: {data['temp']}, Current: {read_temp()}, toaster : {power}")
    
        # サンプリング時間だけ待機
        time.sleep(dt)

    ssr_control(power=False)


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
