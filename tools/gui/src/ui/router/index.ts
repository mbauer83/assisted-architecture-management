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
    { path: '/entities/groups', component: () => import('../views/GroupManagementView.vue'), props: () => ({ axis: 'model-project' }) },
    { path: '/documents', component: () => import('../views/DocumentsView.vue') },
    { path: '/documents/new', component: () => import('../views/DocumentCreateView.vue') },
    { path: '/documents/:id', component: () => import('../views/DocumentDetailView.vue') },
    { path: '/documents/groups', component: () => import('../views/GroupManagementView.vue'), props: () => ({ axis: 'document-collection' }) },
    { path: '/search', component: SearchView },
    { path: '/diagrams', component: DiagramsView },
    { path: '/diagrams/groups', component: () => import('../views/GroupManagementView.vue'), props: () => ({ axis: 'diagram-collection' }) },
    { path: '/diagram/create/matrix', component: () => import('../views/CreateMatrixView.vue') },
    { path: '/diagram/edit/matrix', component: () => import('../views/EditMatrixView.vue') },
    { path: '/diagram/create', component: CreateDiagramView },
    { path: '/diagram/edit', component: EditDiagramView },
    { path: '/diagram', component: DiagramDetailView },
    { path: '/graph', component: GraphExploreView },
    { path: '/graph/layered', component: () => import('../views/LayeredExplorationView.vue') },
    { path: '/viewpoints', component: () => import('../views/ViewpointsManagementView.vue') },
    { path: '/viewpoints/new', component: () => import('../views/ViewpointsManagementView.vue') },
    { path: '/viewpoints/:slug/edit', component: () => import('../views/ViewpointsManagementView.vue') },
    { path: '/viewpoints/matrix', component: () => import('../views/ViewpointMatrixView.vue') },
    { path: '/viewpoints/diagram', component: () => import('../views/ViewpointDiagramView.vue') },
    // Global (enterprise) repo routes — reuse same views with scope param
    { path: '/global/entities', component: EntitiesView, props: () => ({ scope: 'global' }) },
    { path: '/global/diagrams', component: DiagramsView, props: () => ({ scope: 'global' }) },
    { path: '/global/search', redirect: '/search' },
    // Promotion
    { path: '/promote', component: PromoteView },
    // Guided modeling wizard
    { path: '/model/wizard', component: () => import('../views/ModelWizardView.vue') },
    // Assurance (enabled-gated, separate from model nav)
    { path: '/assurance', component: () => import('../views/AssuranceView.vue') },
    { path: '/assurance/browse', component: () => import('../views/AssuranceBrowseView.vue') },
    { path: '/assurance/stpa', component: () => import('../views/AssuranceStpaWizardView.vue') },
    { path: '/assurance/grc', component: () => import('../views/AssuranceGrcWizardView.vue') },
    { path: '/assurance/cast', component: () => import('../views/AssuranceCastWizardView.vue') },
    { path: '/assurance/gsn', component: () => import('../views/AssuranceGsnWizardView.vue') },
    { path: '/assurance/supply-chain', component: () => import('../views/AssuranceSupplyChainWizardView.vue') },
    { path: '/assurance/baselines', component: () => import('../views/AssuranceBaselinesView.vue') },
    { path: '/assurance/diagrams', component: () => import('../views/AssuranceDiagramsView.vue') },
    { path: '/assurance/analyses', redirect: '/assurance/browse' },
  ],
})
