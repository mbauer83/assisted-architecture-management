import { createRouter, createWebHistory } from 'vue-router'
import { defineAsyncComponent } from 'vue'
import HomeView from '../views/HomeView.vue'
import EntitiesView from '../views/EntitiesView.vue'
import EntityDetailView from '../views/EntityDetailView.vue'
import EntityCreateView from '../views/EntityCreateView.vue'
import SearchView from '../views/SearchView.vue'
import DiagramsView from '../views/DiagramsView.vue'
import DiagramDetailView from '../views/DiagramDetailView.vue'
import CreateDiagramView from '../views/CreateDiagramView.vue'
import GraphExploreView from '../views/GraphExploreView.vue'
import EditDiagramView from '../views/EditDiagramView.vue'
import PromoteView from '../views/PromoteView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    // Engagement repo routes
    { path: '/entities', component: EntitiesView },
    { path: '/entity/create', component: EntityCreateView },
    { path: '/entity', component: EntityDetailView },
    { path: '/documents', component: defineAsyncComponent(() => import('../views/DocumentsView.vue')) },
    { path: '/documents/new', component: defineAsyncComponent(() => import('../views/DocumentCreateView.vue')) },
    { path: '/documents/:id', component: defineAsyncComponent(() => import('../views/DocumentDetailView.vue')) },
    { path: '/search', component: SearchView },
    { path: '/diagrams', component: DiagramsView },
    { path: '/diagram/create/matrix', component: defineAsyncComponent(() => import('../views/CreateMatrixView.vue')) },
    { path: '/diagram/edit/matrix', component: defineAsyncComponent(() => import('../views/EditMatrixView.vue')) },
    { path: '/diagram/create', component: CreateDiagramView },
    { path: '/diagram/edit', component: EditDiagramView },
    { path: '/diagram', component: DiagramDetailView },
    { path: '/graph', component: GraphExploreView },
    // Global (enterprise) repo routes — reuse same views with scope param
    { path: '/global/entities', component: EntitiesView, props: () => ({ scope: 'global' }) },
    { path: '/global/diagrams', component: DiagramsView, props: () => ({ scope: 'global' }) },
    { path: '/global/search', redirect: '/search' },
    // Promotion
    { path: '/promote', component: PromoteView },
  ],
})
