import { registerExtension } from '../../lib/diagramAuthoringExtensions'
import { registerViewerExtension } from '../../lib/diagramViewerExtensions'
import AttributeDetailPanel from './AttributeDetailPanel.vue'
import { attachClassifierAttributeRows } from './attributeSelection'
import DatatypeEditor from './DatatypeEditor.vue'

export function register(): void {
  registerExtension('datatype-editor', DatatypeEditor, {
    managedOwnTypes: ['classifier'],
  })
  // Viewer: make classifier attribute rows selectable, with a sidebar detail panel.
  registerViewerExtension('datatype', {
    attachNodeSubParts: attachClassifierAttributeRows,
    detailComponent: AttributeDetailPanel,
  })
}
