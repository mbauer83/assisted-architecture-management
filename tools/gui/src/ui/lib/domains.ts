import type { EntitySummary } from '../../domain'

export const DOMAIN_COLORS = {
  motivation: '#d8c1e4',
  strategy: '#efbd5d',
  common: '#e8e5d3',
  business: '#f4de7f',
  application: '#b6d7e1',
  technology: '#c3e1b4',
} as const

export const DOMAIN_OPTIONS = [
  { key: '', label: 'All' },
  { key: 'motivation', label: 'Motivation' },
  { key: 'strategy', label: 'Strategy' },
  { key: 'common', label: 'Common' },
  { key: 'business', label: 'Business' },
  { key: 'application', label: 'Application' },
  { key: 'technology', label: 'Technology' },
] as const

export const getDomainColor = (domain?: string) =>
  (domain && DOMAIN_COLORS[domain as keyof typeof DOMAIN_COLORS]) || '#cbd5e1'

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
