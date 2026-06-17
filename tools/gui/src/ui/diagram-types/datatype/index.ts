import { registerExtension } from '../../lib/diagramAuthoringExtensions'
import DatatypeEditor from './DatatypeEditor.vue'

export function register(): void {
  registerExtension('datatype-editor', DatatypeEditor, {
    managedOwnTypes: ['classifier'],
  })
}
