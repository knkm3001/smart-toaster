import time
from typing import Final
from collections import deque
from datetime import datetime

# import read_temp_max6755 as max6755
from read_temp import read_temp
from ssr_control import gpio_control, gpio_creanup

# PID制御器のパラメータとサンプリング時間
kp:Final[float] = 10.0  # 比例
ki:Final[float] = 0.05  # 積分
kd:Final[float] = 16.0  # 微分
dt:Final[float] = 1.0   # サンプリング時間[sec]

MV_THRESHOLD:Final[float] = 1000.0 # 操作量の閾値


def run_pid_process(status,profile):
    """
    PID制御の実行関数
    """
    
    try:
        pid = PIDController(kp, ki, kd, dt)
        current_time = 0
        data_file = 'data_'+datetime.now().strftime("%Y%m%d_%H%M") + '.txt'

        for data in profile:
            current_temp = read_temp()
            # current_temp = max6755.read_temp() # max6755を使う場合
            error = data['temp'] - current_temp
            pid.update(error) # PID制御器の更新
            param = pid.get_current_pid_param()

            for key,val in param.items():
                param[key] = round(val,2)
            pot = round(dt*param['mv']/MV_THRESHOLD,2) # power on time [sec]
            
            # TODO 現在のステータスをRedisとかに入れる
            current_data = f"Time: {data['time']}, Target temp: {data['temp']}, Current temp: {current_temp}, Diff temp: {error}, toaster Ton: {pot} [sec], mv:{param['mv']}, vp:{param['vp']}, vi:{param['vi']}, vd:{param['vd']}, integral:{param['integral']}"
            with open(data_file, 'a') as file:
                 file.write(current_data + '\n')
            print(current_data)

            # 操作量の分だけ電源を制御する
            if pot > 0:
                pot = pot if pot > 0.01 else 0.01
                gpio_control(power=True)
                time.sleep(pot) # pwm on
                if pot < dt: 
                    gpio_control(power=False)
                    time.sleep(dt-pot) # pwm off
            else:
                gpio_control(power=False)
                time.sleep(dt)
            current_time += dt
        else:
            gpio_control(power=False)
            status.value = 'finished'
    except KeyboardInterrupt:
        gpio_control(power=False)
        print('error!:',str(e))
        status.value = 'error:' + str(e)
    

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
        self.is_windup = False          # 積分項が飽和状態か(Anti-windup)

        self.use_integral_limit = False # 積分項に加算する値の有効範囲を設定するかどうか
        if self.use_integral_limit:
            self.integral_sec = 180 # 誤差量としてため込む変数の数(=有効範囲)
            self.integral_que = BoundedQueue(self.integral_sec)
        else:
            self.integral = 0.0


    def reset_param(self):
        self.mv = 0
        self.vp = 0
        self.vi = 0
        self.vd = 0
        self.ex_mv = 0.0   # 前回の操作量
        self.ex_err = 0.0  # 前回の誤差量
        self.ex2_err = 0.0 # 前々回の誤差量
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