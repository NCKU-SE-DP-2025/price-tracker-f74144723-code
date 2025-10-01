<template>
  <nav class="navbar">
    <!-- 標題 -->
    <div class="title">
      <RouterLink to="/overview">價格追蹤小幫手</RouterLink>
    </div>

    <!-- 漢堡按鈕 -->
    <button class="hamburger" @click="toggleMenu">
      ☰
    </button>

    <!-- 選單 -->
    <ul :class="['options', menuOpen ? 'open' : '']">
      <li><RouterLink to="/overview" @click="closeMenu">物價概覽</RouterLink></li>
      <li><RouterLink to="/trending" @click="closeMenu">物價趨勢</RouterLink></li>
      <li><RouterLink to="/news" @click="closeMenu">相關新聞</RouterLink></li>
      <li v-if="!isLoggedIn"><RouterLink to="/login" @click="closeMenu">登入</RouterLink></li>
      <li v-else @click="logout">Hi, {{ getUserName }}! 登出</li>
    </ul>
  </nav>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const userStore = useAuthStore()
const isLoggedIn = computed(() => userStore.isLoggedIn)
const getUserName = computed(() => userStore.getUserName)

function logout() {
  userStore.logout()
}

const menuOpen = ref(false)
function toggleMenu() {
  menuOpen.value = !menuOpen.value
}
function closeMenu() {
  menuOpen.value = false
}
</script>

<style scoped>
.navbar {
  display: flex;
  justify-content: space-between; /* 標題左、漢堡右 */
  align-items: center;
  padding: 1em 1.5em;
  background-color: #f3f3f3;
  box-shadow: 0 0 5px #000000;
  position: relative;
}

/* 標題 */
.navbar .title > a {
  font-size: 1.4em;
  font-weight: bold;
  text-decoration: none;
  color: #2c3e50;
}

/* 選單 */
.navbar ul {
  list-style: none;
  display: flex;
  gap: 1em;
}

.navbar li {
  font-size: 1.2em;
}

.navbar li:hover {
  cursor: pointer;
  font-weight: bold;
}

.navbar a {
  text-decoration: none;
  color: #575B5D;
}

/* 漢堡按鈕 */
.hamburger {
  display: none;
  font-size: 1.8em;
  background: none;
  border: none;
  cursor: pointer;
}

/* 小螢幕 (<768px) */
@media (max-width: 767px) {
  .hamburger {
    display: block;
  }

  /* 保持標題與漢堡在同一行 */
  .navbar {
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    height: auto;
  }

  /* 選單垂直堆疊 */
  .navbar ul {
    flex-direction: column;
    display: none;
    width: 100%;
    margin: 0;
    padding: 0;
    background-color: #f3f3f3;
    position: absolute;
    top: 100%; /* 選單在 navbar 下方 */
    left: 0;
    right: 0;
    z-index: 10;
  }

  .navbar ul.open {
    display: flex;
  }

  /* 水平線分隔 */
  .navbar li {
    padding: 0.5em 0;
    border-bottom: 1px solid #ccc;
    text-align: center;
  }

  .navbar li:last-child {
    border-bottom: none;
  }
}
</style>


