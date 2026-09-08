import type { ImportJob } from '../types/import'

const STORAGE_KEY = 'recent_import_jobs'
const MAX_RECENT_JOBS = 10

export function readRecentImportJobs(): ImportJob[] {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    if (!value) return []
    const parsed: unknown = JSON.parse(value)
    return Array.isArray(parsed) ? (parsed as ImportJob[]).slice(0, MAX_RECENT_JOBS) : []
  } catch {
    return []
  }
}

export function rememberImportJob(job: ImportJob): void {
  const jobs = readRecentImportJobs().filter((item) => item.import_job_id !== job.import_job_id)
  localStorage.setItem(STORAGE_KEY, JSON.stringify([job, ...jobs].slice(0, MAX_RECENT_JOBS)))
}
