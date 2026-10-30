import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import { initTheme } from './stores/app'
import './styles/main.css'

initTheme()

createApp(App).use(router).mount('#app')
