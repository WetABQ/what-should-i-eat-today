<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const currentRoute = ref(router.currentRoute.value.path)

router.afterEach((to) => {
  currentRoute.value = to.path
})
</script>

<template>
  <div class="app">
    <header class="header">
      <h1>🍽️ What Should I Eat Today</h1>
      <nav class="nav">
        <router-link to="/menu" :class="{ active: currentRoute === '/menu' }">
          Menu
        </router-link>
        <router-link to="/settings" :class="{ active: currentRoute === '/settings' }">
          Settings
        </router-link>
      </nav>
    </header>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
  background-color: #f5f5f5;
  color: #333;
}

.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.header h1 {
  font-size: 1.5rem;
}

.nav {
  display: flex;
  gap: 1rem;
}

.nav a {
  color: rgba(255,255,255,0.8);
  text-decoration: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  transition: all 0.2s;
}

.nav a:hover,
.nav a.active {
  color: white;
  background: rgba(255,255,255,0.2);
}

.main {
  flex: 1;
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}
</style>
