<template>
  <div class="chart-container">
    <canvas ref="chartCanvas"></canvas>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { Chart, registerables } from 'chart.js'
Chart.register(...registerables)

// props
const props = defineProps({
  data: {
    type: Object,
    required: true
  }
})

// refs
const chartCanvas = ref(null)
let chart = null

// functions
function generateLabels(startDate, endDate, count) {
  const start = new Date(startDate)
  const labels = []
  for (let i = 0; i < count; i++) {
    const monthDate = new Date(start.getFullYear(), start.getMonth() + i, 1)
    labels.push(`${monthDate.getFullYear()}.${monthDate.getMonth() + 1}`)
  }
  return labels
}

function createChart(data) {
  if (!chartCanvas.value) return
  if (chart) chart.destroy()

  const ctx = chartCanvas.value.getContext('2d')
  let prices = data.統計值.split(',').map((p) => parseInt(p, 10))
  let labels = generateLabels(data.時間起點, data.時間終點, prices.length)

  // 處理前導 0
  const firstNonZeroIndex = prices.findIndex((p) => p !== 0)
  if (firstNonZeroIndex > 0) {
    prices = prices.slice(firstNonZeroIndex)
    labels = labels.slice(firstNonZeroIndex)
  }

  // 替換中間的 0
  let lastValid = prices[0]
  const annotations = []
  prices = prices.map((p, i) => {
    if (p === 0) {
      annotations.push({ index: i, price: lastValid })
      return lastValid
    }
    lastValid = p
    return p
  })

  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: data.產品名稱,
          data: prices,
          fill: false,
          borderColor: 'rgb(75, 192, 192)',
          tension: 0.1,
          pointRadius: prices.map((_, i) =>
            annotations.some((a) => a.index === i) ? 5 : 3
          ),
          pointStyle: prices.map((_, i) =>
            annotations.some((a) => a.index === i) ? 'crossRot' : 'circle'
          )
        }
      ]
    },
    options: {
      scales: { y: { beginAtZero: false } },
      animation: { duration: 300 },
      responsive: true,
      maintainAspectRatio: false
    }
  })
}

// lifecycle
onMounted(() => {
  createChart(props.data)
})

onBeforeUnmount(() => {
  if (chart) chart.destroy()
})

// watch data updates
watch(
  () => props.data,
  (newData, oldData) => {
    if (newData !== oldData) {
      createChart(newData)
    }
  }
)
</script>

<style scoped>
.chart-container {
  position: relative;
  margin: auto;
  height: 30vh;
  width: 100%;
}
</style>
