import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import EntitiesView from '../views/EntitiesView.vue'
import EntityDetailView from '../views/EntityDetailView.vue'
import EntityCreateView from '../views/EntityCreateView.vue'
import SearchView from '../views/SearchView.vue'
import DiagramsView from '../views/DiagramsView.vue'
import DiagramDetailView from '../views/DiagramDetailView.vue'
import CreateDiagramView from '../views/CreateDiagramView.vue'
import GraphExploreView from '../views/GraphExploreView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/entities', component: EntitiesView },
    { path: '/entity/create', component: EntityCreateView },
    { path: '/entity', component: EntityDetailView },
    { path: '/search', component: SearchView },
    { path: '/diagrams', component: DiagramsView },
    { path: '/diagram/create', component: CreateDiagramView },
    { path: '/diagram', component: DiagramDetailView },
    { path: '/graph', component: GraphExploreView },
  ],
})
