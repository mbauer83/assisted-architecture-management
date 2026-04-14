import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import EntitiesView from '../views/EntitiesView.vue'
import EntityDetailView from '../views/EntityDetailView.vue'
import SearchView from '../views/SearchView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/entities', component: EntitiesView },
    { path: '/entity', component: EntityDetailView },
    { path: '/search', component: SearchView },
  ],
})
