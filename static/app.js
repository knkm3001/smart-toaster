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
        data: [{ x: 0, y: 0 }]
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
        max: 600, // デフォルト600秒
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
        max: 300,
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
      customPlugin: {
        enabled: true
      },
    },
    onClick: (event) => {
      if (selectedPoint || do_process) return;
      const xValue = temperatureChart.scales.x.getValueForPixel(event.native.offsetX);
      const yValue = temperatureChart.scales.y.getValueForPixel(event.native.offsetY);
      const customData = {
        x: parseInt(xValue),
        y: parseInt(yValue)
      };

      if (getProfileLastData(temperatureChart).x > xValue) return;
      temperatureChart.data.datasets[0].data.push(customData);

      // クリックした点の場所でグラフの右端を変化
      const lastData = getProfileLastData(temperatureChart);
      if (lastData.x != 0){
        const x_end = temperatureChart.scales.x.end;
        chart_max_x = lastData.x < x_end - 150 ? x_end : x_end + 300;
        temperatureChart.options.scales.x.max = chart_max_x        
      }

      console.log(customData);
      console.log(temperatureChart.data.datasets[0].data)

      temperatureChart.update();
    }
  }
});

fetchTemperatureData();

let selectedPoint = null; // ドラッグアンドドロップで掴んだポイント
let do_process = false;
let process_start_timestamp = NaN; // トースターrun時のタイムスタンプ

// 図上で押下したら近くのポイントを取得する
chartElement.addEventListener('mousedown', (event) => {
  if (do_process) return;
  const elements = temperatureChart.getElementsAtEventForMode(event, 'nearest', { intersect: true }, true);
  if (elements.length) {
    selectedPoint = elements[0];
  }
});

// 図上でクリックを離したらポイントを離す
chartElement.addEventListener('mouseup', () => {
  if (do_process) return;
  selectedPoint = null;
});

// 図上でポイントをドラッグしたら動かす
chartElement.addEventListener('mousemove', (event) => {
  const xValue = temperatureChart.scales.x.getValueForPixel(event.offsetX);
  const yValue = temperatureChart.scales.y.getValueForPixel(event.offsetY);
  const coordinatesElement = document.getElementById('coordinates');
  coordinatesElement.textContent = `X: ${xValue.toFixed(2)}, Y: ${yValue.toFixed(2)}`;

  if (selectedPoint) {
    const datasetIndex = selectedPoint.datasetIndex;
    const dataIndex = selectedPoint.index;

    temperatureChart.data.datasets[datasetIndex].data[dataIndex] = { x: parseInt(xValue), y: parseInt(yValue) };
    temperatureChart.update('none');
  }

});

// 右クリックでポイントを消す
chartElement.addEventListener('contextmenu', (event) => {
  if (do_process) return;
  // デフォルトのコンテキストメニューを無効化
  event.preventDefault();

  // クリックされた点を取得
  const elements = temperatureChart.getElementsAtEventForMode(event, 'nearest', { intersect: true }, true);
  if (elements.length) {
    const element = elements[0];
    const datasetIndex = element.datasetIndex;
    const dataIndex = element.index;

    // データセットから点を削除
    temperatureChart.data.datasets[datasetIndex].data.splice(dataIndex, 1);

    // チャートを更新
    temperatureChart.update();
  }
});


function getProfileLastData(chart) {
  return chart.data.datasets[0].data[chart.data.datasets[0].data.length - 1]
}


// 温度データを定期的に取得し、リアルタイムでグラフに追加する
function fetchTemperatureData() {
  fetch('/get_status')
    .then(response => response.json())
    .then(data => {
      console.log(data)
      const coordinatesElement = document.getElementById('temperature');
      coordinatesElement.textContent = `${data.temperature.toFixed(2)} ℃`;

      // 初期値設定
      if(temperatureChart.data.datasets[0].data[0].y == 0){
        temperatureChart.data.datasets[0].data[0].y = data.temperature;
        temperatureChart.update();
      }
      
      // PIDプロセス起動中なら温度をグラフにレンダリングする
      if (do_process) {
        const temperatureData = {
          x: data.timestamp - parseInt(process_start_timestamp / 1000), // sec to sec
          y: data.temperature
        };
        temperatureChart.data.datasets[1].data.push(temperatureData);
        console.log(temperatureData);
        console.log(temperatureChart.data.datasets[1].data)
    
        temperatureChart.update();
      }

    })
    .catch(error => console.error('Error fetching temperature data:', error));
}

// 2秒ごとに温度データを取得する
setInterval(fetchTemperatureData, 2000);

// スタートボタン設定
const startButton = document.getElementById('startButton');
startButton.addEventListener('click', () => {
  do_process = true
  startButton.setAttribute("disabled", true);

  process_start_timestamp = Date.now()
  console.log(do_process)
  console.log(process_start_timestamp)

  fetch('/run_process', {
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
      console.log(data);
    })
    .catch(error => {
      console.error('There was a problem with the fetch operation:', error);
    });
});

// ストップボタン設定
const stopButton = document.getElementById('stopButton');
stopButton.addEventListener('click', () => {
  do_process = false;
  process_start_timestamp = NaN;

  startButton.removeAttribute("disabled");

  // 温度記録から点を削除
  temperatureChart.data.datasets[1].data = [];
  // チャートを更新
  temperatureChart.update();

  fetch('/cancel_process', {
    method: 'GET'
  })
    .then(response => {
      console.log(response);
    })
    .catch(error => {
      console.error(error);
    });
});