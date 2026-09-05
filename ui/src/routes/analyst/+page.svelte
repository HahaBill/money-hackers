<script lang="ts">
  import { onMount } from 'svelte';
  import { getGraph } from '$lib/api/client';
  import { loadDashboard, reportState } from '$lib/api/report';
  import { driverLabel, number } from '$lib/format';
  import type { RunGraph } from '$lib/types';

  let graph = $state<RunGraph | null>(null);
  let type = $state('attribution');

  onMount(async () => {
    const dashboard = await loadDashboard();
    if (dashboard) graph = await getGraph(dashboard.report.run_id);
  });

  const filtered = $derived(graph?.nodes.filter((node) => node.type === type) || []);
</script>

<div class="page analyst-page">
  <header class="page-header">
    <div><h1>Analyst · console</h1><p class="muted">Raw graph vocabulary lives here, away from the owner’s briefing.</p></div>
  </header>

  {#if $reportState.error}
    <p class="negative">{$reportState.error}</p>
  {:else if !graph}
    <p>Loading schema…</p>
  {:else}
    <div class="console">
      <aside>
        <h2>Node types</h2>
        {#each [...new Set(graph.nodes.map((node) => node.type))].sort() as nodeType}
          <button class:active={type === nodeType} onclick={() => (type = nodeType)}>{nodeType}</button>
        {/each}
      </aside>
      <main>
        <div class="query">
          <code>SELECT * FROM nodes WHERE type = '{type}' AND run_id = '{graph.run_id}';</code>
          <span>{filtered.length} rows</span>
        </div>
        <div class="results">
          <table>
            <thead><tr><th>id</th><th>label</th><th>value</th><th>confidence</th><th>provenance</th></tr></thead>
            <tbody>
              {#each filtered as node}
                <tr>
                  <td>{node.id}</td>
                  <td>{driverLabel(node.label)}</td>
                  <td>{typeof node.value === 'object' ? JSON.stringify(node.value) : String(node.value)}</td>
                  <td>{number(node.confidence)}</td>
                  <td>{node.provenance}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </main>
      <aside class="schema">
        <h2>Schema</h2>
        <code>nodes</code><code>edges</code><code>findings</code><code>attributions</code><code>simulations</code><code>directives</code>
        <a href={`/api/runs/${graph.run_id}`} download>Export run JSON</a>
      </aside>
    </div>
  {/if}
</div>

<style>
  .analyst-page { max-width: 100rem; font-family: var(--font-mono); }
  .analyst-page h1, .analyst-page h2, .analyst-page p { font-family: var(--font-sans); }
  .console { display: grid; grid-template-columns: 14rem minmax(0, 1fr) 13rem; min-height: 42rem; gap: 1rem; }
  aside { background: var(--soft); padding: 1rem; }
  aside h2 { font-size: 1rem; }
  aside button { display: block; width: 100%; min-height: 2rem; border: 0; border-radius: 0; padding: 0.3rem 0; text-align: left; }
  aside button.active { color: var(--awning); font-weight: 700; }
  .query { display: flex; justify-content: space-between; gap: 1rem; border: 1px solid var(--line); background: var(--white); padding: 1rem; }
  .query span { color: var(--muted); white-space: nowrap; }
  .results { overflow: auto; margin-top: 1rem; border: 1px solid var(--line); }
  table { width: 100%; min-width: 50rem; border-collapse: collapse; font-size: 0.78rem; }
  th, td { max-width: 22rem; overflow: hidden; border-bottom: 1px solid var(--line); padding: 0.45rem; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
  thead { background: var(--soft); }
  .schema { display: flex; flex-direction: column; gap: 0.5rem; }
  .schema a { margin-top: 1rem; color: var(--awning); font-family: var(--font-sans); font-weight: 700; }
  @media (max-width: 65rem) { .console { grid-template-columns: 11rem minmax(0, 1fr); } .schema { display: none; } }
  @media (max-width: 47.99rem) { .console { grid-template-columns: 1fr; } .console > aside:first-child { display: flex; overflow: auto; gap: 0.5rem; } aside button { width: auto; white-space: nowrap; } }
</style>
