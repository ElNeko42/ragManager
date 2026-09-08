import { request } from './client'

export interface ServiceHealth {
  healthy: boolean
  detail?: string | null
}

export interface HealthReport {
  healthy: boolean
  services: Record<string, ServiceHealth>
}

/**
 * Returns whether every backing service is answering.
 *
 * A degraded stack answers with an error status and a body describing which
 * service failed, so the failing report is read rather than thrown away.
 */
export async function readHealth(): Promise<HealthReport> {
  try {
    return await request<HealthReport>('/health/')
  } catch (error) {
    if (error instanceof Error && 'body' in error) {
      const body = (error as { body: unknown }).body
      if (isHealthReport(body)) {
        return body
      }
    }
    throw error
  }
}

/**
 * Reports whether a parsed body has the shape of a health report.
 */
function isHealthReport(value: unknown): value is HealthReport {
  return typeof value === 'object' && value !== null && 'services' in value
}
