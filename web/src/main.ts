import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import MenuView from './views/MenuView.vue'
import SettingsView from './views/SettingsView.vue'

const routes = [
  { path: '/', redirect: '/menu' },
  { path: '/menu', component: MenuView },
  { path: '/settings', component: SettingsView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const app = createApp(App)
app.use(router)
app.mount('#app')
