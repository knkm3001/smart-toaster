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
今回はトースターの温度と加熱時間をラズベリーパイによって管理したいので、このサーモスタットとタイマーを取り外し、直流で接続する。  
つまり、オーブントースターを電源に接続したら加熱が始まるようにする。  
  
画像は廣瀬無線電機 Hi-Rose HR-T121を使用。  

### RasPiのハードウェア周り
1. SSRの準備
  延長ケーブルを改造し、SSRで制御できるようにする。ヒューズも装着。
1. MAX31855の準備
  プレッドボードとと熱電対を接続
1. SSRとMAX31855をRaspberryPiのGPIOに接続し回路を組む

参考: https://learn.adafruit.com/thermocouple/python-circuitpython

### ラズパイ環境構築
1. Raspberry Pi立ち上げ
   - SSH有効化
   - SPI有効化  
   - apt更新
1. `docker`, `docker compose`をinstall
  `docker compose build` でコンテナイメージを作成
1. 熱電対のテスト  
    `docker compose exec api-server python /app/src/read_temp.py` を実行。適切な温度が取得できているか確認。
1. SSRのテスト  
    オーブントースター(その他任意の家電製品でも可)をSSRに接続する。
    `docker compose exec api-server python /app/src/ssr_control.py` を実行し、ON/OFFを繰り返しできているか確認。
1. アプリケーション起動  
    `docker compose up -d`
    - web app: `<raspi-ip>:5000`
    - redis web ui: `<raspi-ip>:8081`
