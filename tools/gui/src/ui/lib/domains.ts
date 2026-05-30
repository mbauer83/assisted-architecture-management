import type { EntitySummary } from '../../domain'
import { DOMAIN_NAMES, type DomainName } from '../../domain/types.generated'

type DomainDisplayConfig = { color: string; label: string }

const DOMAIN_CONFIG: Partial<Record<DomainName, DomainDisplayConfig>> = {
  motivation:     { color: '#d8c1e4', label: 'Motivation' },
  strategy:       { color: '#efbd5d', label: 'Strategy' },
  common:         { color: '#e8e5d3', label: 'Common' },
  business:       { color: '#f4de7f', label: 'Business' },
  application:    { color: '#b6d7e1', label: 'Application' },
  technology:     { color: '#c3e1b4', label: 'Technology' },
  implementation: { color: '#f4c896', label: 'Implementation' },
  sysml:          { color: '#c0d4ee', label: 'SysML v2' },
}

export const DOMAIN_COLORS: Partial<Record<DomainName, string>> = Object.fromEntries(
  (Object.entries(DOMAIN_CONFIG) as [DomainName, DomainDisplayConfig][]).map(([k, v]) => [k, v.color]),
)

export const DOMAIN_OPTIONS = [
  { key: '' as string, label: 'All' },
  ...DOMAIN_NAMES
    .filter(n => n !== 'unknown')
    .map(name => ({
      key: name,
      label: DOMAIN_CONFIG[name]?.label ?? (name.charAt(0).toUpperCase() + name.slice(1)),
    })),
]

export const getDomainColor = (domain?: string) =>
  (domain ? DOMAIN_COLORS[domain as DomainName] : undefined) ?? '#cbd5e1'

export const getDomainLabel = (domain: string) =>
  DOMAIN_OPTIONS.find(option => option.key === domain)?.label ?? domain

export const getEntityConnectionTotal = (entity: EntitySummary) =>
  (entity.conn_in ?? 0) + (entity.conn_sym ?? 0) + (entity.conn_out ?? 0)

export const friendlyEntityId = (id: string) => {
  const parts = id.split('.')
  return parts.length > 2 ? parts.slice(2).join('.') : id
}

export const softTint = (hex: string, strength = 0.82) => {
  const value = hex.replace('#', '')
  if (value.length !== 6) return hex
  const mix = (offset: number) =>
    Math.round(parseInt(value.slice(offset, offset + 2), 16) * (1 - strength) + 255 * strength)
      .toString(16)
      .padStart(2, '0')
  return `#${mix(0)}${mix(2)}${mix(4)}`
}
