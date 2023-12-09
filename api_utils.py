import numpy as np
from scipy.interpolate import interp1d

def generate_interp_data(data):
    """
    APIのペイロードで渡されたプロファイルデータを線形補完し、時間ごとの目標温度を作成する

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
