import os
from pydantic import BaseModel, Field
from typing import List, Optional

class PIDParams(BaseModel):
    """
    PID制御のパラメータを表すデータクラス

    Attributes
    ----------
    kp : float, default=10.0
        比例ゲイン
    ki : float, default=0.1
        積分ゲイン
    kd : float, default=18.0
        微分ゲイン
    dt : int, default=1.0
        サンプリング時間 [sec]
    mv_threshold : float, default=1000.0
        操作量(mv)の閾値
    """
    kp: float = Field(default_factory=lambda: float(os.getenv('KP', '10.0')))
    ki: float = Field(default_factory=lambda: float(os.getenv('KI', '0.1')))
    kd: float = Field(default_factory=lambda: float(os.getenv('KD', '18.0')))
    dt: int   = Field(default_factory=lambda: int(os.getenv('DT', '1')))
    mv_threshold: float = Field(default_factory=lambda: float(os.getenv('MV_THRESHOLD', '1000.0')))


class ProfilePoint(BaseModel):
    """
    プロファイルの変化点を表すデータクラス

    Attributes
    ----------
    time : int
        時間。>=0
    target_temp : float
        ある時間における目標温度。>=0
    """
    time: int = Field(...,  ge=0)
    target_temp: float = Field(...,  ge=0)


class StatusData(BaseModel):
    """
    ある瞬間のプロセスの状態を表すデータクラス

    Attributes
    ----------
    time_passed : float
        プロセス開始からの経過時間 [sec] 
    timestamp : float
        状態の記録時のUnixタイムスタンプ
    target_temp : float
        その時点での目標温度
    current_temp : float
        現在の温度
    power_on_time : float
        PID制御サイクルにおいて電源がONの時間 [sec]
    pid_process_status : str
        プロセスの現在の状態を示すステータス
    vp : float
        比例項における現在の計算結果
    vi : float
        積分項における現在の計算結果
    vd : float
        微分項における現在の計算結果
    mv : float
        現在の操作量。mv = vp + vi + vd
    integral : float
        エラーの累積
    """
    time_passed: float = Field(...)
    timestamp: float = Field(...)
    target_temp: float = Field(...)
    current_temp: float = Field(...)
    power_on_time: float = Field(...)
    pid_process_status: str = Field(...)
    vp: float = Field(...)
    vi: float = Field(...)
    vd: float = Field(...)
    mv: float = Field(...)
    integral: float = Field(...)



class Recipe(BaseModel):
    pid_param: Optional[PIDParams] = None
    profile: List[ProfilePoint]