import { registerExtension } from '../../lib/diagramAuthoringExtensions'
import ActivityStepEditor from './ActivityStepEditor.vue'

export function register(): void {
  registerExtension('activity-steps', ActivityStepEditor, {
    managedOwnTypes: ['action', 'decision', 'fork', 'partition', 'note'],
  })
}
