<template>
    <div class="trending-table">
        <table>
            <thead>
                <tr>
                    <th rowspan="2">年份</th>
                    <th v-for="month in months" :key="month">{{ month }}</th>
                </tr>
            </thead>
            <tbody>
                <template v-for="year in years" :key="year">
                    <tr>
                        <td>{{ year }}</td>
                        <template v-for="(value, monthIndex) in getYearData(year)" :key="year + '-month-' + monthIndex">
                            <td>{{ valueDisplay(value) }}</td>
                        </template>
                    </tr>
                </template>
            </tbody>
        </table>
    </div>
</template>

<script>
import { ref, computed, watch, onBeforeMount } from 'vue'

export default {
  props: {
    data: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    const yearData = ref({})

    // 固定月份
    const months = computed(() => [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ])

    // 動態年份
    const years = computed(() => {
      const startYear = new Date(props.data.時間起點).getFullYear()
      const endYear = new Date(props.data.時間終點).getFullYear()
      const yearsArr = []
      for (let year = startYear; year <= endYear; year++) {
        yearsArr.push(year)
      }
      return yearsArr
    })

    // 依年份取資料
    function getYearData(year) {
      return yearData.value[year]
    }

    // 初始化資料
    function processInitData() {
      const startMonth = new Date(props.data.時間起點).getMonth() + 1
      const endMonth = new Date(props.data.時間終點).getMonth() + 1
      const startYear = new Date(props.data.時間起點).getFullYear()
      const endYear = new Date(props.data.時間終點).getFullYear()
      yearData.value = {}

      const allValues = props.data.統計值.split(',')

      for (let year = startYear; year <= endYear; year++) {
        const yearPrices = []
        for (let month = 1; month <= 12; month++) {
          if (year === startYear && month < startMonth) {
            yearPrices.push('0')
          } else if (year === endYear && month > endMonth) {
            yearPrices.push('0')
          } else {
            const index = month + (year - startYear) * 12 - startMonth
            yearPrices.push(allValues[index])
          }
        }
        yearData.value[year] = yearPrices
      }
    }

    // 顯示數值
    function valueDisplay(value) {
      return value === '0' ? '-' : value
    }

    // 監聽 props.data 變化
    watch(
      () => props.data,
      (newVal) => {
        if (newVal) processInitData()
      },
      { deep: true }
    )

    // created hook
    onBeforeMount(() => {
      processInitData()
    })

    return {
      yearData,
      months,
      years,
      getYearData,
      processInitData,
      valueDisplay
    }
  }
}

</script>

<style scoped>
.trending-table {
    margin-top: 2em;
}

table {
    width: 100%;
    border-collapse: collapse;
}

th,
td {
    border: 1px solid #ccc;
    padding: 0.5em;
    text-align: center;
}
</style>