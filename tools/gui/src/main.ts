import { createApp } from 'vue'
import App from './ui/App.vue'
import { router } from './ui/router'
import { modelServiceKey } from './ui/keys'
import { makeModelService } from './application/ModelService'
import { makeHttpModelRepository } from './adapters/http/HttpModelRepository'

const app = createApp(App)
app.use(router)
app.provide(modelServiceKey, makeModelService(makeHttpModelRepository()))
app.mount('#app')
