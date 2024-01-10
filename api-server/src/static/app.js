

const defaultMaxY = 300;
const defaultMaxX = 600;
let pidProcessIsRunning = false; // トースターRUNボタンによりPID制御が起動している
let selectedPoint = null; // ドラッグアンドドロップで掴んだポイント
let latestStatusTime = 0; // フロント側で持っている最新のステータスデータの発行時間
let processStartUT = null; // processがスタートしたときのunix time
let processStatus = null; // processの状態
const dt = 1.0;

// chart作成
temperatureChart = createChart();

fetchStatus({isInit: true}); //初期化データ取得

// 2秒ごとに温度データを取得する
setInterval(fetchStatus, 2000);

createToasterRunButton();
createStopButton();

setupClearButton();
setupDownloadChartData();
setupFileUpload();
setupSaveRecipe();

/**
 * funcs
 */

function clearParams(){
  pidProcessIsRunning = false;
  process_start_timestamp = NaN;
  selectedPoint = null;
  latestStatusTime = 0;
  processStartUT = null;
  processStatus = null;
  fetchStatus({isInit: true});
}

// 温度データを定期的に取得し、リアルタイムでグラフに追加する
function fetchStatus(isInit=false) {

  const getStatusEndPoint = isInit ? '/get_status?isInit=True' : `/get_status?minKey=${latestStatusTime}`
  console.log(getStatusEndPoint)
  fetch(getStatusEndPoint)
    .then(response => {
      if (!response.ok) {
        return response.text().then(text => { throw new Error(text) });
      }
      return response.json(); 
    })
    .then(data => {
      console.log(`data`)
      console.log(data)

      // 表示部初期化
      document.getElementById('temperature').textContent = `current temperature: ${data.current_temp.toFixed(2)} ℃`;
      document.getElementById('processStatus').textContent = `current process: ${data.pid_process_status}`;

      // 初期化時
      if(isInit){
        processStatus = data.pid_process_status
        kp = data.pid_param.kp;
        ki = data.pid_param.ki;
        kd = data.pid_param.kd;
        temperatureChart.data.datasets[0].data = [];
        temperatureChart.data.datasets[1].data = [];
        document.getElementById('toasterOutPut').textContent = `current output: 0.0 %`;
        document.getElementById('coordinates').textContent = `Time: 0.0 [sec], Temperature: ${data.current_temp.toFixed(2)} [℃]`;
        
        if(processStatus !== 'not running'){
          pidProcessIsRunning = true
          disabledToasterRunButton();
        }

        // プロファイルをグラフにレンダリング
        if(data.profile.length !== 0){
          data.profile.forEach(e => {
            temperatureChart.data.datasets[0].data.push(e);
          });
        }

        // データをグラフにレンダリング
        if(data.status_data.length !== 0){
          processStartUT = data.status_data.find(item => item.time_passed === 0).timestamp
          data.status_data.forEach(e => {
            // 温度をグラフにレンダリングする
            const tempData = {
              x: parseInt(e.timestamp - processStartUT), // sec to sec
              y: e.current_temp
            };
            temperatureChart.data.datasets[1].data.push(tempData);
          });
        } 
          // 各<input>要素にデフォルト値を設定
          document.getElementById('kpInput').value = data.pid_param.kp; // 比例ゲインのデフォルト値
          document.getElementById('kiInput').value = data.pid_param.ki; // 積分ゲインのデフォルト値
          document.getElementById('kdInput').value = data.pid_param.kd; // 微分ゲインのデフォルト値
      }

      if(data.pid_process_status == 'not running'){
        // PIDプロセスがまだ起動していないとき
        
        if(processStatus != 'not running'){
          // UI以外の方法で初期化された場合、UI側をリセットする
          clearParams();
          processStatus = data.pid_process_status
        }
        
        // 初期値設定
        temperatureChart.data.datasets[0].data[0] = {x:0, y:data.current_temp};
        temperatureChart.update();

      }else{
        // PIDプロセスが起動中、もしくは終了後

        processStatus = data.pid_process_status

        const firstItem = data.status_data.find(item => item.time_passed === 0);
        if(firstItem !== undefined){
          processStartUT = firstItem.timestamp;
          console.log('processStartUT')
          console.log(processStartUT)
        }
        const latestItem = data.status_data[data.status_data.length -1]
        latestStatusTime = latestItem.time_passed

        if(data.pid_process_status == 'running' && !isInit){
          console.log('running')

          data.status_data.forEach(e => {
            const tempData = {
              x: parseInt(e.timestamp - processStartUT), // sec to sec
              y: e.current_temp
            };

            document.getElementById('toasterOutPut').textContent = `current output: ${(latestItem.power_on_time*100).toFixed(1)} %`;

            let dataset = temperatureChart.data.datasets[1].data;
            let isDuplicate = dataset.some(data => data.x === tempData.x && data.y === tempData.y);

            if (!isDuplicate) {
                dataset.push(tempData);
            }
          });

        }else{
          // finished or killed
          console.log('finished or killed')

          const tempData = {
            x: parseInt(data.current_timestamp - processStartUT), // sec to sec
            y: data.current_temp
          };
          let dataset = temperatureChart.data.datasets[1].data;
          let isDuplicate = dataset.some(data => data.x === tempData.x && data.y === tempData.y);

          if (!isDuplicate) {
              dataset.push(tempData);
          }
        }

        latestChartItem = temperatureChart.data.datasets[1].data[temperatureChart.data.datasets[1].data.length -1]

        console.log('latestChartItem')
        console.log(latestChartItem)

        // 右端を拡張
        if(latestChartItem.x >= temperatureChart.options.scales.x.max - 60){
          temperatureChart.options.scales.x.max += 60;
        }

        // 上端を拡張
        if(latestChartItem.y >= temperatureChart.options.scales.y.max - 20){
          temperatureChart.options.scales.y.max += 20;   
        }

        console.log('tempData')
        console.log(temperatureChart.data.datasets[1].data)
    
        temperatureChart.update();

      }
           

    })
    .catch(error => {
      console.log("error!: " + error.message)
      alert("Error: " + error.message);
    });  
}


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


function createChart(){
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
        if (selectedPoint || pidProcessIsRunning) return;
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
      },
    },
    plugins: [],
  });

  // 図上で押下したら近くのポイントを取得する
  chartElement.addEventListener('mousedown', (event) => {
    if (pidProcessIsRunning) return;
    const elements = temperatureChart.getElementsAtEventForMode(event, 'nearest', { intersect: true }, true);
    if (elements.length && elements[0].index != 0) { // 0番目は動かさない
      selectedPoint = elements[0];
    }
  });

  // 図上でクリックを離したらポイントを離す
  chartElement.addEventListener('mouseup', () => {
    if (pidProcessIsRunning) return;
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
    if (pidProcessIsRunning) return;
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

  return temperatureChart;

}


function initProcessStatus(){
  fetch('/status_clear', {
    method: 'GET'
  })
    .then(response => {
      if (!response.ok) {
        return response.text().then(text => { throw new Error(text) });
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
      alert("error!: " + error);
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


// プロセス実行中は以下のボタンを使用できない
function disabledToasterRunButton(){
  document.getElementById('toasterRunButton').setAttribute("disabled", true);
  document.getElementById('clear').setAttribute("disabled", true);
  document.getElementById('uploadRecipe').setAttribute("disabled", true);
  document.getElementById('kpInput').setAttribute("disabled", true);
  document.getElementById('kiInput').setAttribute("disabled", true);
  document.getElementById('kdInput').setAttribute("disabled", true);

}

function createToasterRunButton(){
  // トースターRunボタンの設定
  const toasterRunButton = document.getElementById('toasterRunButton');
  toasterRunButton.addEventListener('click', () => {
    pidProcessIsRunning = true;
    
    disabledToasterRunButton();

    // 右端を調整
    const profileLastData = getLastData(temperatureChart,0); // profileの最後のデータ取得
    temperatureChart.options.scales.x.max = parseInt(profileLastData.x/60 + 1)*60
    temperatureChart.update();
    
    let payload = {
      "profile": temperatureChart.data.datasets[0].data,
    }

    const kp = document.getElementById('kpInput').value;
    const ki = document.getElementById('kiInput').value;
    const kd = document.getElementById('kdInput').value;

    const isValidParam = [kp,ki,kd,dt].every(v => !isNaN(parseFloat(v)) && isFinite(v));
    if(isValidParam){
      payload['pid_param'] = {
        "kp": kp,
        "ki": ki,
        "kd": kd,
        "dt": dt,
      }
    }
    console.log(payload)

    fetch('/run_process', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })
      .then(response => {
        if (!response.ok) {
          return response.text().then(text => { throw new Error(text) });
        }
        return response.json(); 
      })
      .then(data => {
        console.log(data);
      })
      .catch(error => {
        console.error(error);
        alert("error!: " + error);
      });
  });
}


function createStopButton(){
  // プロセスキャンセルボタン設定
  const toasterStopButton = document.getElementById('toasterStopButton');
  toasterStopButton.addEventListener('click', () => {
    fetch('/kill_process', {
      method: 'GET'
    })
    .then(response => {
      if (!response.ok) {
        return response.text().then(text => { throw new Error(text) });
      }
      return response.json(); 
    })
    .then(data => {
      console.log(data);
      if(data['message'] == 'Task killed'){
        pidProcessIsRunning = false;
        document.getElementById('clear').removeAttribute("disabled");
        document.getElementById('processStatus').textContent = `current process: killed`;
      }else{
        pidProcessIsRunning = false;
        document.getElementById('clear').removeAttribute("disabled");
      }
    })
    .catch(error => {
      console.error(error);
      alert("error!: " + error);
    });
  });
}


// clear button
function setupClearButton(){
  document.getElementById('clear').addEventListener('click', () => {
    temperatureChart.options.scales.x.max = defaultMaxX;
    temperatureChart.options.scales.y.max = defaultMaxY;
    temperatureChart.data.datasets[0].data = [];
    temperatureChart.data.datasets[1].data = [];
    pidProcessIsRunning = false;
    initProcessStatus();
    toasterRunButton.removeAttribute("disabled");
    clearParams(); // UI側のパラメータクリア
    temperatureChart.update();
    console.log('clear!')
  });
}

// downloadChartData button
function setupDownloadChartData(){
  document.getElementById('downloadChartData').addEventListener('click', () => {
    fetch('/get_chart_data', {
      method: 'GET'
    })
    .then(response => {
      if (!response.ok) {
        return response.text().then(text => { throw new Error(text) });
      }
      return response.json(); 
    })
    .then(data => {
      const jsonData = {
        status_data: data.status_data,
        recipe: data.recipe,
        interp_profile: data.interp_profile
      }
      downloadJson(jsonData, 'chart_data.json');
    })
    .catch(error => {
      console.log("error!: " + error.message)
      alert("Error: " + error.message);
    });  
  });
}

//ファイルアップロード周り
function setupFileUpload(){

  const fileInput = document.getElementById('fileInput');
  document.getElementById('uploadRecipe').addEventListener('click', () => {
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

            if(!('profile' in jsonContent)){
              throw new Error("'profile' key does not exist in the JSON object.");
            }
            temperatureChart.data.datasets[0].data = jsonContent.profile;
            
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
            
            // pid_paramはあればそれつかう
            if('pid_param' in jsonContent && ['kp','ki','kd'].every(key => key in jsonContent.pid_param)){
              document.getElementById('kpInput').value = jsonContent.pid_param.kp;
              document.getElementById('kiInput').value = jsonContent.pid_param.ki;
              document.getElementById('kdInput').value = jsonContent.pid_param.kd;
            }
  
        } catch (error) {
            console.error('Error parsing JSON file:');
            console.log(error)
            alert('Invalid JSON file.');
        }
    };
    fileReader.readAsText(file);
    fileInput.value = ""; // リセット
  });
}

// Recipe 保存
function setupSaveRecipe(){
  document.getElementById('saveRecipe').addEventListener('click', () => {
    const kp = document.getElementById('kpInput').value;
    const ki = document.getElementById('kiInput').value;
    const kd = document.getElementById('kdInput').value;
    jsonData = {
      profile: temperatureChart.data.datasets[0].data,
      pid_param: {
        "kp": kp,
        "ki": ki,
        "kd": kd,
        "dt": dt,
      }
    }
    downloadJson(jsonData, 'recipe.json');
  });
}