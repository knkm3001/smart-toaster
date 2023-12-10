const defaultMaxY = 300;
const defaultMaxX = 600;
let do_pid_process = false;
let do_record_temp = false;
let process_start_timestamp = NaN; // トースターrun時のタイムスタンプ

const chartElement = document.getElementById('temperatureChart');
const temperatureChart = new Chart(chartElement, {
  type: 'line',
  data: {
    datasets: [
      {
        label: 'Profile',
        borderColor: 'rgba(75, 192, 192, 1)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        fill: false,
        pointRadius: 6,
        data: []
      },
      {
        label: 'Current Temp',
        borderColor: 'rgba(255, 99, 132, 1)',
        backgroundColor: 'rgba(255, 99, 132, 1)',
        fill: false,
        pointRadius: 3,
        data: []
      }
    ]
  },
  options: {
    animation: false,
    layout: {
      padding: {
        left: 0, // グラフ左端の余白を0に設定
        bottom: 0 // グラフ下端の余白を0に設定
      },
    },
    scales: {
      x: {
        min: 0,
        max: defaultMaxX, // デフォルト600秒
        type: 'linear',
        title: {
          display: true,
          text: 'Time (s)'
        },
        ticks: {
          stepSize: 60,
          beginAtZero: true  // x軸のメモリ値を0から始めるように設定
        }
      },
      y: {
        min: 0,
        max: defaultMaxY,
        title: {
          display: true,
          text: 'Temperature (°C)'
        },
        ticks: {
          stepSize: 20,
          beginAtZero: true  // x軸のメモリ値を0から始めるように設定
        }
      }
    },
    plugins: {
      tooltip: {
        enabled: false
      },
      mousePosition: {
        enabled: true
      },
    },
    onClick: (event) => {
      if (selectedPoint || do_pid_process) return;
      const xValue = temperatureChart.scales.x.getValueForPixel(event.native.offsetX);
      const yValue = temperatureChart.scales.y.getValueForPixel(event.native.offsetY);
      const customData = {
        x: parseInt(xValue),
        y: parseInt(yValue)
      };

      if (getLastData(temperatureChart,0).x > xValue) return;
      temperatureChart.data.datasets[0].data.push(customData);

      // クリックした点の場所でグラフの右端を変化
      const lastProfileData = getLastData(temperatureChart,0);
      if (lastProfileData.x != 0){
        const x_end = temperatureChart.scales.x.end;
        chart_max_x = lastProfileData.x < x_end - 150 ? x_end : x_end + 300;
        temperatureChart.options.scales.x.max = chart_max_x        
      }

      console.log(customData);
      console.log(temperatureChart.data.datasets[0].data)

      temperatureChart.update();
    }
  },
  plugins: [],
});

fetchStatus(); //初期化データ取得

let selectedPoint = null; // ドラッグアンドドロップで掴んだポイント

// 図上で押下したら近くのポイントを取得する
chartElement.addEventListener('mousedown', (event) => {
  if (do_pid_process) return;
  const elements = temperatureChart.getElementsAtEventForMode(event, 'nearest', { intersect: true }, true);
  if (elements.length && elements[0].index != 0) { // 0番目は動かさない
    selectedPoint = elements[0];
  }
});

// 図上でクリックを離したらポイントを離す
chartElement.addEventListener('mouseup', () => {
  if (do_pid_process) return;
  selectedPoint = null;
});

// 図上でポイントをドラッグしたら動かす
chartElement.addEventListener('mousemove', (event) => {
  const xValue = Math.max(temperatureChart.scales.x.getValueForPixel(event.offsetX),0);
  const yValue = Math.max(temperatureChart.scales.y.getValueForPixel(event.offsetY),0); 
  const coordinatesElement = document.getElementById('coordinates');
  coordinatesElement.textContent = `Time: ${xValue.toFixed(1)} [sec], Temperature: ${yValue.toFixed(1)} [℃]`;

  if (selectedPoint) {
    const datasetIndex = selectedPoint.datasetIndex;
    const dataIndex = selectedPoint.index;

    temperatureChart.data.datasets[datasetIndex].data[dataIndex] = { x: parseInt(xValue), y: parseInt(yValue) };
    temperatureChart.update('none');
  }

});

// 右クリックでポイントを消す
chartElement.addEventListener('contextmenu', (event) => {
  if (do_pid_process) return;
  // デフォルトのコンテキストメニューを無効化
  event.preventDefault();

  // クリックされた点を取得
  const elements = temperatureChart.getElementsAtEventForMode(event, 'nearest', { intersect: true }, true);
  if (elements.length && elements[0].index != 0) { // 0番目は消さない
    const element = elements[0];
    const datasetIndex = element.datasetIndex;
    const dataIndex = element.index;

    // データセットから点を削除
    temperatureChart.data.datasets[datasetIndex].data.splice(dataIndex, 1);

    // チャートを更新
    temperatureChart.update();
  }
});

// dataの最後を取得
function getLastData(chart,dataIndex) {
  return chart.data.datasets[dataIndex].data[chart.data.datasets[dataIndex].data.length - 1]
}

// dataの最大値を取得
function getMaxData(chart,dataIndex,key) {
  const data = chart.data.datasets[dataIndex].data
  const maxIndex = data.reduce((maxIndex, current, currentIndex) => {
    return current[key] > data[maxIndex][key] ? currentIndex : maxIndex;
  }, 0);
  return data[maxIndex];
}

// 温度データを定期的に取得し、リアルタイムでグラフに追加する
function fetchStatus() {
  fetch('/get_current_status')
    .then(response => response.json())
    .then(data => {
      console.log(data)

      // 表示部
      document.getElementById('temperature').textContent = `current temperature: ${data.current_temp.toFixed(2)} ℃`;
      document.getElementById('processStatus').textContent = `current process: ${data.process_status}`;

      // 初期値設定
      if(temperatureChart.data.datasets[0].data.length == 0){
        temperatureChart.data.datasets[0].data[0] = {x:0, y:data.current_temp};
        temperatureChart.update();
      }
      
      // 温度をグラフにレンダリングする
      if (do_record_temp) {
        const currentTempData = {
          x: data.timestamp - parseInt(process_start_timestamp / 1000), // sec to sec
          y: data.current_temp
        };
        temperatureChart.data.datasets[1].data.push(currentTempData);
        console.log('current data',currentTempData)
        
        // 右端を拡張
        if(currentTempData.x >= temperatureChart.options.scales.x.max - 60){
          temperatureChart.options.scales.x.max += 60;
        }

        // 上端を拡張
        if(currentTempData.y >= temperatureChart.options.scales.y.max - 20){
          temperatureChart.options.scales.y.max += 20;   
        }
    
        temperatureChart.update();
      }

    })
    .catch(error => console.error('Error fetching temperature data:', error));
}

// 2秒ごとに温度データを取得する
setInterval(fetchStatus, 2000);

// トースターランボタンの設定
const startButton = document.getElementById('startButton');
startButton.addEventListener('click', () => {
  do_pid_process = true;
  do_record_temp = true;
  
  // プロセス実行中は、プロセス実行ボタンとclearボタンは押せない
  startButton.setAttribute("disabled", true);
  document.getElementById('clear').setAttribute("disabled", true);

  // 右端を調整
  const profileLastData = getLastData(temperatureChart,0); // profileの最後のデータ取得
  temperatureChart.options.scales.x.max = parseInt(profileLastData.x/60 + 1)*60
  temperatureChart.update();

  // TODO サーバ側とフロント側でタイムスタンプが別なので統一する
  process_start_timestamp = Date.now()
  console.log(process_start_timestamp)
  
  const payload = {
    "profile": temperatureChart.data.datasets[0].data,
    "pid_param": { // TODO マジックナンバー。あとでここは変更できるようにする
      "kp": 10.0,
      "ki": 0.05,
      "kd": 18.0,
      "dt": 1.0
    }
  }

  fetch('/run_process', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })
    .then(response => {
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      return response.json();
    })
    .then(data => {
      console.log(data);
    })
    .catch(error => {
      console.error('There was a problem with the fetch operation:', error);
    });
});

// プロセスキャンセルボタン設定
const stopButton = document.getElementById('stopButton');
stopButton.addEventListener('click', () => {
  fetch('/kill_process', {
    method: 'GET'
  })
    .then(response => {
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      return response.json();
    })
    .then(data => {
      console.log(data);
      if(data['message'] == 'Task killed'){
        do_pid_process = false;
        document.getElementById('clear').removeAttribute("disabled");
        document.getElementById('processStatus').textContent = `current process: killed`;
      }else{
        do_pid_process = false;
        document.getElementById('clear').removeAttribute("disabled");
      }
    })
    .catch(error => {
      console.error(error);
    });
});


function initProcessStatus(){
  fetch('/status_clear', {
    method: 'GET'
  })
    .then(response => {
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      return response.json();
    })
    .then(data => {
      console.log(data);
      if(data.message == 'status is cleared'){
        document.getElementById('processStatus').textContent = `current process: not running`;
      }
    })
    .catch(error => {
      console.error(error);
    });
}


function downloadJson(jsonData, fileName) {
  const dataStr = JSON.stringify(jsonData, null, 2); // JSONデータを整形して文字列に変換
  const blob = new Blob([dataStr], { type: 'application/json;charset=utf-8' }); // Blobオブジェクトを作成
  const url = URL.createObjectURL(blob); // BlobオブジェクトからURLを生成

  const link = document.createElement('a'); // ダウンロード用のリンク要素を作成
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click(); // リンク要素をクリックしてダウンロードを実行
  document.body.removeChild(link); // リンク要素を削除
  URL.revokeObjectURL(url); // BlobオブジェクトのURLを解放
}

document.getElementById('saveProfile').addEventListener('click', () => {
  // TODO redisのデータをダウンロードするようにする
  const fileName = 'profile.json';
  jsonData = temperatureChart.data.datasets[0].data;
  downloadJson(jsonData, fileName);
});

const fileInput = document.getElementById('fileInput');
document.getElementById('uploadProfile').addEventListener('click', () => {
  fileInput.click();
});

// ファイルアップロード周り
fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  if (!file) {
      return;
  }
  const fileReader = new FileReader();
  fileReader.onload = async (event) => { // fileReaderにファイルを噛ませたあとのコールバック関数
      try {
          const jsonContent = JSON.parse(event.target.result);
          console.log('JSON Content:');
          console.log(jsonContent)
          temperatureChart.data.datasets[0].data = jsonContent;
          
          // 右端を拡張
          const profileLastData = getLastData(temperatureChart,0); // profileの最後のデータ取得
          if(profileLastData.x >= defaultMaxX - 60){
            temperatureChart.options.scales.x.max = parseInt(profileLastData.x/60 + 1)*60
          }

          // 上端を拡張
          const maxProfileData = getMaxData(temperatureChart,0,'y'); // profileの最大の温度を取得
          console.log('max',maxProfileData);
          if(maxProfileData.y >= defaultMaxY - 20){
            temperatureChart.options.scales.y.max = parseInt(maxProfileData.y/20 + 1)*20   
          }else{
            temperatureChart.options.scales.y.max = defaultMaxY;
          }

          temperatureChart.update();

      } catch (error) {
          console.error('Error parsing JSON file:');
          console.log(error)
          alert('Invalid JSON file.');
      }
  };
  fileReader.readAsText(file);
  fileInput.value = ""; // リセット
});


document.getElementById('downloadChartData').addEventListener('click', () => {
  fetch('/get_pid_proc_status', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(temperatureChart.data.datasets[0].data)
  })
  .then(response => {
    if (!response.ok) {
      throw new Error('Network response was not ok');
    }
    return response.json();
  })
  .then(data => {
    const jsonData = [data,temperatureChart.data.datasets[1].data];
    const fileName = 'chart_data.json';
    downloadJson(jsonData, fileName);
  })
  .catch(error => {
    console.error('Error:', error);
  });  
});

document.getElementById('clear').addEventListener('click', () => {
  temperatureChart.options.scales.x.max = defaultMaxX;
  temperatureChart.options.scales.y.max = defaultMaxY;
  temperatureChart.data.datasets[0].data = [];
  temperatureChart.data.datasets[1].data = [];
  do_pid_process = false;
  do_record_temp = false;
  initProcessStatus();
  startButton.removeAttribute("disabled");
  fetchStatus(); //初期化データ取得
  temperatureChart.update();
  console.log('clear!')
});
