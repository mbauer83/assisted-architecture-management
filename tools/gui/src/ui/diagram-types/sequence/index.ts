import { registerExtension } from '../../lib/diagramAuthoringExtensions'
import SequenceEditor from './SequenceEditor.vue'

export function register(): void {
  registerExtension('sequence-editor', SequenceEditor, {
    managedOwnTypes: ['lifeline', 'message', 'grouping', 'note'],
  })
}
