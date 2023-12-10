import numpy as np

def generate_interp_profile(data:list,dt:int=1):
    """
    APIのペイロードで渡されたプロファイルデータを線形補完し、サンプリング時間ごとの目標温度を作成する

    Args:
        data (list): [{'x':int,'y':int}...] xが時間、yが温度
        dt (int): サンプリング時間
    Returns:
        list: [{'time':int,'temp':int}...] xが時間、yが温度
    """

    x_new = np.array([])
    y_new = np.array([])

    is_invalid_data = False
    ex_coord = None
    for coord in data:
        if ex_coord is None:
            if coord['x'] != 0: # 必ずx=0始まりであること
                is_invalid_data = True
                break
            else:
                ex_coord = coord
                continue
        else:
            if coord['x'] < ex_coord['x']:
                is_invalid_data = True
                break
            # 線形補間
            x_points = (ex_coord['x'],coord['x'])
            y_points = (ex_coord['y'],coord['y'])
            x_generated = np.arange(x_points[0], x_points[1], dt)
            y_generated = np.interp(x_generated, x_points, y_points)
            x_new = np.concatenate([x_new, x_generated]) 
            y_new = np.concatenate([y_new, y_generated])
            ex_coord = coord
        
    if is_invalid_data:
        return []
    else:
        return [{'time':x,'temp':round(y,2)} for x,y in zip(x_new,y_new)]
