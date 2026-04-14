import type { InjectionKey } from 'vue'
import type { ModelService } from '../application/ModelService'

export const modelServiceKey: InjectionKey<ModelService> = Symbol('modelService')
