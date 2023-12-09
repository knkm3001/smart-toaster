# smart toaster

## 環境構築
### 使用パーツ
下記パーツを調達
- 一般的なオーブントースター
- Raspberry Pi 3 or 4(OSはRasbian lightを想定)
- adafruit MAX31855
- k型熱電対
- ソリッドステート・リレー(gpio出力電圧で動く電圧容量のもの)
- 家庭用電源用の手頃な延長ケーブル(トースターのワット数に耐用したもの)
- ヒューズ
- プレッドボード
- ジャンパワイヤ複数本

### トースター改造
一般的なトースターにはサーモスタット(出力ワット数のつまみ)とタイマーが接続されている。
これらのパーツが電流を適宜管理することで、トースター内部の温度と加熱時間をコントロールしている。
今回はトースターの温度と加熱時間をラズベリーパイによって管理したいので、このサーモスタットとタイマーを取り外し、直流で接続する。つまり、オーブントースターを電源に接続したら加熱が始まるようにする。  
  
画像は廣瀬無線電機 Hi-Rose HR-T121を使用。  

### RasPiのハードウェア周り
1. SSRの準備
  延長ケーブルを改造し、SSRで制御できるようにする。ヒューズも装着。
1. MAX31855の準備
  プレッドボードとと熱電対を接続
1. SSRとMAX31855をRaspberryPiのGPIOに接続し回路を組む

参考: https://learn.adafruit.com/thermocouple/python-circuitpython

### ラズパイ環境構築
1. Raspberry Pi を立ち上げ、SSH等で接続、SPIを有効化
1. apt周りの更新と、python環境の構築  
    `$ sudo apt update && sudo apt upgrade && sudo apt install -y git python3 python3-pip python3-numpy python3-scipy`
1. pythonライブラリのインストール  
    `$ https://github.com/knkm3001/smart-toaster.git && cd smart-toaster && pip install -r requirements.txt`
1. 熱電対のテスト
    `python read_temp.py` を実行。適切な温度が取得できているか確認。
1. SSRのテスト
    オーブントースター(その他任意の家電製品でも可)をSSRに接続する。
    `python ssr_control.py` を実行し、ON/OFFを繰り返しできているか確認。

### アプリケーション実行
1. `python app.py`
