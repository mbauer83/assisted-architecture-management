import type { AttrTypeRef, Classifier } from './useDatatypeModel'

export type TypeOptionGroup = 'Primitives' | 'This diagram' | 'Engagement' | 'Enterprise'

export interface CatalogClassifier {
  readonly type_id: string
  readonly label: string
  readonly scope: string
  readonly host_diagram_id: string
}

export interface TypeOption {
  readonly key: string
  readonly label: string
  readonly group: TypeOptionGroup
  readonly ref: AttrTypeRef
}

export function optionKey(ref: AttrTypeRef | undefined): string {
  if (!ref) return ''
  return ref.kind === 'primitive' ? `primitive:${ref.name}` : `classifier:${ref.id}`
}

export function refFromOptionKey(key: string, options: readonly TypeOption[]): AttrTypeRef | undefined {
  return options.find((option) => option.key === key)?.ref
}

export function buildTypeOptions(
  primitiveTypes: readonly string[],
  localClassifiers: readonly Classifier[],
  catalogClassifiers: readonly CatalogClassifier[],
  diagramId: string,
): TypeOption[] {
  const options: TypeOption[] = []
  const seen = new Set<string>()
  const append = (option: TypeOption) => {
    if (seen.has(option.key)) return
    seen.add(option.key)
    options.push(option)
  }
  primitiveTypes.forEach((name) => append({
    key: `primitive:${name}`,
    label: name,
    group: 'Primitives',
    ref: { kind: 'primitive', name },
  }))
  localClassifiers.forEach((classifier) => append({
    key: `classifier:${classifier.id}`,
    label: classifier.label ?? classifier.id,
    group: 'This diagram',
    ref: { kind: 'classifier', id: classifier.id },
  }))
  catalogClassifiers.forEach((classifier) => append({
    key: `classifier:${classifier.type_id}`,
    label: classifier.label,
    group: classifier.host_diagram_id === diagramId
      ? 'This diagram'
      : classifier.scope === 'enterprise' ? 'Enterprise' : 'Engagement',
    ref: { kind: 'classifier', id: classifier.type_id },
  }))
  return options
}

export function replaceUniqueConstraint(
  constraints: readonly string[][],
  index: number,
  names: readonly string[],
): string[][] {
  return constraints.map((constraint, i) => i === index ? [...names] : [...constraint])
}

export function removeUniqueConstraint(
  constraints: readonly string[][],
  index: number,
): string[][] | undefined {
  const remaining = constraints.filter((_, i) => i !== index).map((constraint) => [...constraint])
  return remaining.length ? remaining : undefined
}
