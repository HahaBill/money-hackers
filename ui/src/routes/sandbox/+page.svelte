<script lang="ts">
  import { onMount } from 'svelte';
  import { loadDashboard, reportState } from '$lib/api/report';
  import { driverLabel, money, monthLabel, percent } from '$lib/format';

  onMount(() => loadDashboard());
</script>

{#if $reportState.loading}
  <div class="page status-message"><h1>Loading modeled actions…</h1></div>
{:else if $reportState.error}
  <div class="page status-message"><p>{$reportState.error}</p></div>
{:else if $reportState.dashboard}
  {@const dashboard = $reportState.dashboard}
  {@const simulations = dashboard.report.simulations || []}
  <div class="page sandbox-page">
    <header class="page-header">
      <div>
        <h1>Assumptions · {monthLabel(dashboard.report.period)} as the base</h1>
        <p class="muted">Modeled by the deterministic driver graph. Nothing here writes to the ledger.</p>
      </div>
    </header>

    <div class="formula desktop-only"><strong>fx</strong> Profit recalculates through the driver graph; assumptions travel with every result.</div>

    <section class="scenario-grid">
      <div class="row heading"><span>Assumption</span><span>Change</span><span>Effect on profit</span><span>Range</span></div>
      {#each simulations as simulation}
        <div class="row">
          <div><strong>{driverLabel(simulation.leaf)}</strong><small>{simulation.assumption}</small></div>
          <span class="mono">{percent(simulation.delta_pct, true)}</span>
          <strong class="mono positive">{money(simulation.delta_profit, true)}</strong>
          <div>
            {#if simulation.sweep_range}
              <span class="mono">{money(simulation.sweep_range[0], true)} … {money(simulation.sweep_range[1], true)}</span>
              <div class="range"><i style={`width:${Math.max(8, simulation.confidence * 100)}%`}></i></div>
            {:else}
              <span class="muted">fixed assumption</span>
            {/if}
          </div>
        </div>
      {:else}
        <div class="card">No modeled intervention cleared the positive-impact filter.</div>
      {/each}
    </section>

    <section class="solver card">
      <div><h2>What would it take?</h2><p>Inverse solving needs the next deterministic simulation endpoint. Existing modeled actions remain available above.</p></div>
      <button disabled>Solve</button>
    </section>
  </div>
{/if}

<style>
  .sandbox-page { max-width: 92rem; }
  .formula { border: 1px solid var(--line); background: var(--white); padding: 0.65rem 0.85rem; font-family: var(--font-mono); }
  .formula strong { margin-right: 0.7rem; color: var(--muted); }
  .scenario-grid { margin-top: 1rem; border: 1px solid var(--line); }
  .row { display: grid; grid-template-columns: minmax(14rem, 2fr) 0.7fr 1fr 1.4fr; align-items: center; min-height: 4.4rem; border-bottom: 1px solid var(--line); }
  .row > * { padding: 0.7rem 0.9rem; }
  .row > * + * { border-left: 1px solid var(--line); }
  .row.heading { min-height: 2.6rem; background: var(--soft); font-weight: 700; }
  .row small { display: block; color: var(--muted); }
  .range { height: 0.55rem; margin-top: 0.35rem; border-radius: 0.25rem; background: var(--soft); }
  .range i { display: block; height: 100%; border-radius: inherit; background: var(--stonks); }
  .solver { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-top: 2rem; }
  .solver h2 { margin-bottom: 0.25rem; }
  .solver p { margin-bottom: 0; color: var(--muted); }
  @media (max-width: 47.99rem) {
    .scenario-grid { border: 0; }
    .row { grid-template-columns: 1fr 1fr; margin-bottom: 0.75rem; border: 1px solid var(--line); background: var(--white); }
    .row.heading { display: none; }
    .row > * + * { border-left: 0; }
    .row > div:first-child { grid-column: 1 / -1; border-bottom: 1px solid var(--line); }
  }
</style>
