<script lang="ts">
  import { onMount } from 'svelte';
  import SheetView from '$lib/components/month/SheetView.svelte';
  import { loadDashboard, reportState } from '$lib/api/report';
  import { monthLabel } from '$lib/format';

  onMount(() => {
    loadDashboard();
  });
</script>

{#if $reportState.loading}
  <div class="page status-message" aria-live="polite">
    <div><h1>Reading the latest period…</h1><p>Checking the numbers and loading their evidence.</p></div>
  </div>
{:else if $reportState.error}
  <div class="page status-message">
    <div>
      <h1>The latest analysis isn’t reachable.</h1>
      <p>{$reportState.error}</p>
      <button class="primary" onclick={() => loadDashboard(true)}>Try again</button>
    </div>
  </div>
{:else if $reportState.dashboard}
  {@const dashboard = $reportState.dashboard}
  <div class="page month-page">
    <header class="desktop-head">
      <div>
        <p class="breadcrumb">{dashboard.business.name} / Financial workbook</p>
        <h1>{monthLabel(dashboard.report.period)}</h1>
        <p class="muted">
          {dashboard.report.status === 'complete' ? 'Reconciled analysis' : dashboard.report.status}
          · {dashboard.graph_counts.nodes} traceable nodes
        </p>
      </div>
    </header>

    {#if dashboard.report.status === 'blocked'}
      <section class="blocked" role="alert">
        <h2>{monthLabel(dashboard.report.period)} doesn’t add up yet.</h2>
        <p>The analysis stopped before drawing conclusions. Open the checks and correct the source data.</p>
        <a href="/queue">Show the checks →</a>
      </section>
    {:else}
      <SheetView {dashboard} />
    {/if}
  </div>
{/if}

<style>
  .month-page {
    max-width: 105rem;
  }

  .desktop-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .desktop-head h1,
  .desktop-head p {
    margin-bottom: 0;
  }

  .breadcrumb {
    color: var(--muted);
    font-size: 0.82rem;
  }

  .blocked {
    border: 1.5px solid var(--tomato);
    border-radius: 0.625rem;
    background: var(--white);
    padding: 1.5rem;
  }

  .blocked a {
    color: var(--awning);
    font-weight: 700;
  }

</style>
