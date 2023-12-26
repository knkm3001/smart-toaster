
"""
redis model
キー名 (redisの型): 説明 (元のpythonの型) 
- pid_process_status (str): PID制御プロセスが自身の状態を伝えるためのステータス(str) (w: PID制御プロセス)
    - not running: PID制御が起動していない
    - running: PID制御が起動中
    - finished: PID制御正常終了
    - killed: PID制御強制終了
    - error: 何らかの理由でエラー
- pid_param (str): PIDパラメータ(dict)
    - kp (float):
    - ki (float):
    - kd (float):
    - id (int): サンプリング時間。基本は1sec
- profile (str): APIリクエストで渡されたオリジナルのパラメータ(list)
    [{'time':int,'temp':int}...]
- interp_profile (str): recipe.profile を線形補間したもの(list)
    [{'time':int,'temp':int}...]
- status_data (list): PID制御を開始してからの各パラメータデータを記録したもの。数字キーは開始してからの時刻(秒)を示す(dict)
    - time_passed (int): 経過時間
    - target_temp (float): 目的温度
    - current_temp (float): ステータス取得時の温度
    - timestamp (float): ステータス取得時のlinux time
    - power_on_time (float): 出力
    - mv (float): 操作量
    - vp (float): 比例量
    - vi (float): 積分量
    - vd (float): 微分量
    - integral (float): 積分量のうち溜め込んだ素の値
"""
import redis

def redis_client():
    return redis.Redis(host='redis', port=6379, db=0)