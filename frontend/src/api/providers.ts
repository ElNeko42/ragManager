import { requestJson } from './client'

export interface Provider {
  id: string
  label: string
  base_url: string
  docs_url: string
  needs_key: boolean
}

export interface ProviderModel {
  id: string
  looks_like_embedding: boolean
}

export interface ModelListing {
  models: ProviderModel[]
  listing_supported: boolean
  filtered: boolean
  hidden: number
  detail?: string
}

export interface Measurement {
  vector_size: number
  duration_ms: number
}

interface EndpointRequest {
  base_url: string
  api_key?: string
  collection?: string
}

interface ModelListRequest extends EndpointRequest {
  provider?: string
  include_all?: boolean
}

/**
 * Returns the endpoints offered as a starting point.
 *
 * They only save typing a URL: anything that speaks the same shape is typed in
 * instead, which is the same field.
 */
export function listProviders(): Promise<{ providers: Provider[] }> {
  return requestJson<{ providers: Provider[] }>('/api/providers/', 'GET', undefined)
}

/**
 * Asks an endpoint which models it serves.
 *
 * Only the embedding models come back: a chat model picked from the same list
 * registers a collection that can never index anything, and the mistake would
 * not surface until a document had been through the queue. Pass include_all to
 * reach a model whose name gives nothing away.
 *
 * An endpoint dedicated to one model has no list to give and says so rather
 * than failing, because typing the name and measuring it settles the question
 * either way.
 */
export function listProviderModels(payload: ModelListRequest): Promise<ModelListing> {
  return requestJson<ModelListing>('/api/providers/models/', 'POST', payload)
}

/**
 * Measures what one model actually answers with.
 *
 * The width is the one field nobody can guess and the one that makes every
 * stored vector unusable when it is wrong, so it is measured rather than
 * typed.
 */
export function probeModel(
  payload: EndpointRequest & { model_name: string }
): Promise<Measurement> {
  return requestJson<Measurement>('/api/providers/probe/', 'POST', payload)
}
