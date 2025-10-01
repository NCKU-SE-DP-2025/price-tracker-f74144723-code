<template>
    <div class="wrapper">
        <h1>各類商品物價概覽</h1>
        <h3 v-if="!isLoading" class="subtitle">資料更新時間：{{updateTime}}</h3>
        <div class="prices">
            <CategoryPrice class="category" v-for="category in categoryList" :key="category"
                :category="category" :isLoading="isLoading" :errorMessage="errorMessage" :priceData="getPriceData(category)"></CategoryPrice>
        </div>
    </div>
</template>

<script>
import { computed, onMounted } from 'vue'
import CategoryPrice from '@/components/CategoryPrice.vue'
import Categories from '@/constants/categories'
import { usePricesStore } from '@/stores/prices'

export default {
  name: 'PriceOverview',
  components: {
    CategoryPrice
  },
  setup() {
    const store = usePricesStore()

    // category list
    const categoryList = computed(() => Object.keys(Categories))

    // 來自 store 的狀態
    const isLoading = computed(() => store.isLoading)
    const errorMessage = computed(() => store.errorMessage)
    const updateTime = computed(() => store.updatedTime)

    // 方法
    function getPriceData(category) {
      return store.getPricesByCategory(category)
    }

    // 初始化載入
    onMounted(() => {
      store.fetchPrices()
    })

    return {
      categoryList,
      isLoading,
      errorMessage,
      updateTime,
      getPriceData
    }
  }
}

</script>

<style scoped>
.wrapper{
    padding: 3em 5em;
    background: #f3f3f3;
    min-height: calc(100vh - 4.5em);
    height: calc(100% - 4.5em);
    box-sizing: border-box;
}
.prices{
    display: flex;
    justify-content: space-around;
    flex-wrap: wrap;
}
.category{
    margin: 1em;
    flex-grow: 1;
}
.subtitle{
    font-weight: normal;
    margin-top: .5em;
}
</style>