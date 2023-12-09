# smart toaster

## 環境構築
### 使用パーツ
下記パーツを調達
- 手頃なオーブントースター(廣瀬無線電機 Hi-Rose HR-T121を使用)
- Raspberry Pi 3 or 4(OSはRasbian lightを想定)
- adafruit MAX31855
- k型熱電対
- ソリッドステート・リレー(gpio出力電圧で動く電圧容量のもの)
- 手頃な延長ケーブル(トースターのワット数に対応したもの)
- ジャンパワイヤ複数本
- ヒューズ()

### トースター改造
下記は廣瀬無線電機 Hi-Rose HR-T121を想定。  
オーブントースターを電源に接続したら動作するようにする。  
そのため、サーモスタット(出力ワット数のつまみ)、タイマーを除去し、直流で接続する。  

### 電気周り
1. 延長ケーブルを改造し、SSRで制御できるようにする。ヒューズも装着。
1. adafruit MAX31855を使えるように回路を組む
1. SSRとMAX31855をRaspberryPiのGPIOに接続 

参考: https://learn.adafruit.com/thermocouple/python-circuitpython

### ラズパイ環境構築
1. Raspberry Pi を立ち上げ、SSH等で接続、SPIを有効化
1. apt周りの更新と、python環境の構築  
    `$ sudo apt update && sudo apt upgrade && sudo apt install -y git python3 python3-pip python3-numpy python3-scipy`
1. pythonライブラリのインストール  
    `$ https://github.com/knkm3001/smart-toaster.git && cd smart-toaster && pip install -r requirements.txt`
1. 熱電対のテスト
