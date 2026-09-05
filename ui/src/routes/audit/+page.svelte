<script lang="ts">
  import { onMount } from 'svelte';
  import { getGraph } from '$lib/api/client';
  import { loadDashboard, reportState } from '$lib/api/report';
  import { driverLabel, money, monthLabel, number, percent } from '$lib/format';
  import type { GraphNode, RunGraph } from '$lib/types';

  let graph = $state<RunGraph | null>(null);
  let graphError = $state<string | null>(null);
  let tab = $state<'ledger' | 'graph'>('ledger');
  let selected = $state<GraphNode | null>(null);

  onMount(async () => {
    const current = await loadDashboard();
    if (!current) return;
    try {
      graph = await getGraph(current.report.run_id);
    } catch (cause) {
      graphError = cause instanceof Error ? cause.message : 'Could not load the graph.';
    }
  });

  function valueText(node: GraphNode): string {
    if (typeof node.value === 'number') {
      return node.unit === 'USD' ? money(node.value, true) : number(node.value);
    }
    if (typeof node.value === 'string') return node.value;
    if (node.type === 'baseline' && node.value && typeof node.value === 'object') {
      const z = (node.value as Record<string, unknown>).z;
      return typeof z === 'number' ? `z ${number(z)}` : 'baseline';
    }
    return node.type;
  }

  function actor(node: GraphNode): string {
    if (node.provenance === 'raw') return 'Reader';
    if (node.provenance === 'inferred' || node.type === 'finding') return 'Analyst';
    if (node.provenance === 'retrieved') return 'Analyst';
    return 'Checker';
  }
</script>

{#if $reportState.loading}
  <div class="page status-message"><h1>Opening the audit trail…</h1></div>
{:else if $reportState.error}
  <div class="page status-message"><p>{$reportState.error}</p></div>
{:else if $reportState.dashboard}
  {@const dashboard = $reportState.dashboard}
  <div class="page audit-page">
    <header class="page-header">
      <div>
        <h1>{monthLabel(dashboard.report.period)} · what the analyst did</h1>
        <p class="muted">Every number, inference, source, and revision stays on record.</p>
      </div>
    </header>

    <div class="tabs" role="tablist" aria-label="Audit views">
      <button class:active={tab === 'ledger'} onclick={() => (tab = 'ledger')}>Ledger</button>
      <button class:active={tab === 'graph'} onclick={() => (tab = 'graph')}>Graph</button>
    </div>

    {#if graphError}
      <p class="negative">{graphError}</p>
    {:else if !graph}
      <p>Loading graph…</p>
    {:else if tab === 'ledger'}
      <div class="ledger-wrap">
        <table>
          <thead><tr><th>Who</th><th>Did</th><th>Value</th><th>Confidence</th></tr></thead>
          <tbody>
            {#each graph.nodes.slice().reverse() as node}
              <tr onclick={() => (selected = node)} class:selected={selected?.id === node.id}>
                <td class:analyst={actor(node) === 'Analyst'}>{actor(node)}</td>
                <td><strong>{driverLabel(node.label)}</strong><span>{node.type} · {node.method || node.provenance}</span></td>
                <td class="mono">{valueText(node)}</td>
                <td class="mono">{percent(node.confidence * 100)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else}
      <div class="graph-view">
        {#each ['raw', 'deterministic', 'retrieved', 'inferred'] as provenance}
          <section>
            <h2>{provenance === 'raw' ? 'Reader' : provenance === 'deterministic' ? 'Checker' : 'Analyst'}</h2>
            <div class="node-list">
              {#each graph.nodes.filter((node) => node.provenance === provenance).slice(0, 18) as node}
                <button
                  class:active={selected?.id === node.id}
                  class:analyst-node={provenance === 'inferred' || provenance === 'retrieved'}
                  onclick={() => (selected = node)}
                >
                  <span>{driverLabel(node.label)}</span>
                  <small class="mono">{valueText(node)}</small>
                </button>
              {/each}
            </div>
          </section>
        {/each}
      </div>
    {/if}

    {#if selected}
      <aside class="detail card">
        <div>
          <span class="eyebrow">{selected.type} · {selected.provenance}</span>
          <h2>{driverLabel(selected.label)}</h2>
          <p class="mono">{selected.id}</p>
        </div>
        <div>
          <strong>{valueText(selected)}</strong>
          <p>{selected.formula || selected.method || 'Recorded in the calculation graph.'}</p>
          <p class="muted">{selected.inputs.length} direct input{selected.inputs.length === 1 ? '' : 's'} · {percent(selected.confidence * 100)} confidence</p>
        </div>
      </aside>
    {/if}
  </div>
{/if}

<style>
  .audit-page { max-width: 95rem; }
  .tabs { display: flex; gap: 1.2rem; margin-bottom: 1rem; border-bottom: 1px solid var(--line); }
  .tabs button { min-height: 2.5rem; border: 0; border-radius: 0; padding: 0 0.2rem; color: var(--muted); }
  .tabs button.active { border-bottom: 3px solid var(--chalk); color: var(--chalk); font-weight: 700; }
  .ledger-wrap { overflow: auto; border: 1px solid var(--line); }
  table { width: 100%; min-width: 48rem; border-collapse: collapse; }
  th, td { border-bottom: 1px solid var(--line); padding: 0.55rem 0.75rem; text-align: left; }
  thead { background: var(--soft); }
  tbody tr { cursor: pointer; }
  tbody tr:hover, tbody tr.selected { background: color-mix(in srgb, var(--awning) 7%, transparent); }
  td:nth-child(1) { width: 7rem; font-weight: 700; }
  td:nth-child(2) span { display: block; color: var(--muted); font-size: 0.8rem; }
  td.analyst { color: var(--awning); }
  .graph-view { display: grid; grid-template-columns: repeat(4, minmax(12rem, 1fr)); gap: 1rem; overflow: auto; }
  .graph-view section { min-width: 12rem; }
  .graph-view h2 { border-bottom: 1px solid var(--line); padding-bottom: 0.5rem; text-transform: capitalize; }
  .node-list { display: grid; gap: 0.5rem; }
  .node-list button { display: grid; min-height: 3.5rem; text-align: left; background: var(--white); }
  .node-list button.analyst-node { border-color: var(--awning); }
  .node-list button.active { outline: 3px solid color-mix(in srgb, var(--awning) 35%, transparent); }
  .node-list small { color: var(--muted); }
  .detail { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin-top: 1rem; }
  .detail h2, .detail p { margin-bottom: 0.35rem; }
  @media (max-width: 47.99rem) {
    .detail { grid-template-columns: 1fr; gap: 0.5rem; }
    .graph-view { grid-template-columns: repeat(4, 15rem); }
  }
</style>
