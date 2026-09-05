import { derived, get, writable } from 'svelte/store';
import { getDashboard, listRuns } from './client';
import type { Dashboard, RunSummary } from '$lib/types';

type ReportState = {
  loading: boolean;
  dashboard: Dashboard | null;
  runs: RunSummary[];
  error: string | null;
};

const initial: ReportState = { loading: false, dashboard: null, runs: [], error: null };
export const reportState = writable<ReportState>(initial);
export const dashboard = derived(reportState, ($state) => $state.dashboard);

let pending: Promise<Dashboard | null> | null = null;

export function loadDashboard(force = false): Promise<Dashboard | null> {
  const current = get(reportState);
  if (!force && current.dashboard) return Promise.resolve(current.dashboard);
  if (!force && pending) return pending;
  reportState.update((state) => ({ ...state, loading: true, error: null }));
  pending = (async () => {
    try {
      const runs = await listRuns();
      if (!runs.length) throw new Error('No completed analysis runs are available yet.');
      const selected =
        runs.find((run) => run.status === 'complete' && run.graph_node_count > 0) ||
        runs.find((run) => run.status === 'complete') ||
        runs[0];
      const result = await getDashboard(selected.run_id);
      reportState.set({ loading: false, dashboard: result, runs, error: null });
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not load the analysis.';
      reportState.set({ loading: false, dashboard: null, runs: [], error: message });
      return null;
    } finally {
      pending = null;
    }
  })();
  return pending;
}
