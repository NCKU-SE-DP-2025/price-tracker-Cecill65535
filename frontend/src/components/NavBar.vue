<template>
  <nav class="navbar">
    <div class="title">
      <RouterLink to="/overview">價格追蹤小幫手</RouterLink>
    </div>

    <button class="menu-toggle" @click="toggleMenu">☰</button>

    <ul :class="['options', { active: menuOpen }]">
      <li><RouterLink to="/overview">物價概覽</RouterLink></li>
      <li><RouterLink to="/trending">物價趨勢</RouterLink></li>
      <li><RouterLink to="/news">相關新聞</RouterLink></li>
      <li v-if="!isLoggedIn"><RouterLink to="/login">登入</RouterLink></li>
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
const logout = () => userStore.logout()

const menuOpen = ref(false)
const toggleMenu = () => (menuOpen.value = !menuOpen.value)
</script>

<style scoped>
.navbar {
  display: flex;
  justify-content: space-between;
  background-color: #f3f3f3;
  padding: 1.5em;
  height: 4.5em;
  width: 100%;
  align-items: center;
  box-shadow: 0 0 5px #000000;
  position: fixed;
  top: 0;
  left: 0;
  z-index: 1000;
}

.title > a {
  font-size: 1.4em;
  font-weight: bold;
  color: #2c3e50 !important;
  text-decoration: none;
}

.options {
  list-style: none;
  display: flex;
  justify-content: space-around;
}

.options li {
  color: #575B5D;
  margin: 0 0.5em;
  font-size: 1.2em;
}

.options li:hover {
  cursor: pointer;
  font-weight: bold;
}

.navbar a {
  text-decoration: none;
  color: #575B5D;
}

.menu-toggle {
  display: none;
  background: none;
  border: none;
  font-size: 1.8em;
  color: #2c3e50;
  cursor: pointer;
}

@media (max-width: 768px) {
  .menu-toggle {
    display: block;
  }

  .options {
    display: none;
    flex-direction: column;
    background-color: #f3f3f3;
    width: 100%;
    position: absolute;
    top: 4.5em;
    left: 0;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    padding: 1em 0;
  }

  .options.active {
    display: flex;
  }

  .options li {
    margin: 0.7em 0;
  }
}
</style>
