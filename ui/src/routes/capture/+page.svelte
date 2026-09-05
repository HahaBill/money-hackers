<script lang="ts">
  import { onMount } from 'svelte';
  import { loadDashboard, reportState } from '$lib/api/report';
  import { money, monthLabel } from '$lib/format';
  import type { VerifyItem } from '$lib/types';

  let selected = $state<VerifyItem | null>(null);
  onMount(async () => {
    const dashboard = await loadDashboard();
    selected = dashboard?.report.verify?.[0] || null;
  });
</script>

{#if $reportState.loading}
  <div class="page status-message"><h1>Opening capture review…</h1></div>
{:else if $reportState.error}
  <div class="page status-message"><p>{$reportState.error}</p></div>
{:else if $reportState.dashboard}
  {@const dashboard = $reportState.dashboard}
  {@const items = dashboard.report.verify || []}
  <div class="page capture-page">
    <header class="page-header">
      <div>
        <h1>Capture review · {monthLabel(dashboard.report.period)}</h1>
        <p class="muted">Exceptions from the imported workbook and receipt checks.</p>
      </div>
      <button disabled={!items.length}>Accept all checked</button>
    </header>

    <div class="tabs" aria-label="Capture sources">
      <button class="active">Receipts</button>
      <button>Statements</button>
      <button>Matches</button>
    </div>

    <div class="review-table">
      <table>
        <thead>
          <tr><th></th><th>Source</th><th>Amount</th><th>Status</th><th>Check</th></tr>
        </thead>
        <tbody>
          {#each items as item}
            <tr class:selected={selected?.node === item.node} onclick={() => (selected = item)}>
              <td><input type="checkbox" aria-label={`Select ${item.entity}`} /></td>
              <td>{item.entity}</td>
              <td class="mono">{money(item.gap_dollars)}</td>
              <td class="negative">needs a look</td>
              <td>{item.detail || item.rule.replaceAll('_', ' ')}</td>
            </tr>
          {:else}
            <tr class="empty-row">
              <td colspan="5">No capture exceptions are attached to this reconciled run.</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <section class="detail card">
      {#if selected}
        <div class="document" aria-hidden="true">
          {#each Array(10) as _, index}<span style={`width:${55 + (index % 4) * 10}%`}></span>{/each}
        </div>
        <div>
          <span class="eyebrow">{selected.rule.replaceAll('_', ' ')}</span>
          <h2>{selected.entity}</h2>
          <dl>
            <dt>Gap</dt><dd class="mono">{money(selected.gap_dollars)}</dd>
            <dt>Check</dt><dd>{selected.detail}</dd>
            <dt>Counter-explanation</dt><dd>{selected.counter_explanation}</dd>
          </dl>
          <div class="actions"><button class="primary">Review source</button><button>Dismiss</button></div>
        </div>
      {:else}
        <div class="empty-detail">
          <h2>Everything attached to this run passed its checks.</h2>
          <p>The review table only shows real extraction or reconciliation exceptions.</p>
        </div>
      {/if}
    </section>
  </div>
{/if}

<style>
  .capture-page { max-width: 96rem; }
  .tabs { display: flex; gap: 1.5rem; border-bottom: 1px solid var(--line); }
  .tabs button { min-height: 2.7rem; border: 0; border-radius: 0; padding: 0 0.15rem; color: var(--muted); }
  .tabs button.active { border-bottom: 3px solid var(--chalk); color: var(--chalk); font-weight: 700; }
  .review-table { overflow: auto; margin-top: 1rem; border: 1px solid var(--line); }
  table { width: 100%; min-width: 55rem; border-collapse: collapse; }
  th, td { border-bottom: 1px solid var(--line); padding: 0.65rem 0.75rem; text-align: left; }
  thead { background: var(--soft); }
  tbody tr:not(.empty-row) { cursor: pointer; }
  tbody tr:hover, tbody tr.selected { background: color-mix(in srgb, var(--awning) 7%, transparent); }
  th:first-child, td:first-child { width: 3rem; text-align: center; }
  .empty-row td { height: 7rem; color: var(--muted); text-align: center; }
  .detail { display: grid; grid-template-columns: 22rem minmax(0, 1fr); gap: 2rem; min-height: 20rem; margin-top: 1.5rem; }
  .document { display: grid; align-content: space-around; border: 1px solid var(--line); background: var(--paper); padding: 2rem; }
  .document span { display: block; height: 2px; background: var(--muted); opacity: 0.55; }
  dl { display: grid; grid-template-columns: 10rem 1fr; gap: 0.5rem 1rem; }
  dt { color: var(--muted); }
  dd { margin: 0; }
  .actions { display: flex; gap: 0.6rem; margin-top: 1.25rem; }
  .empty-detail { align-self: center; grid-column: 1 / -1; text-align: center; }
  .empty-detail p { color: var(--muted); }
</style>
