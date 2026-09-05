<script lang="ts">
  import { onMount } from 'svelte';
  import { loadDashboard, reportState } from '$lib/api/report';
  import BusinessHeader from '$lib/components/BusinessHeader.svelte';
  import { driverLabel, money, monthLabel } from '$lib/format';

  onMount(() => loadDashboard());
</script>

{#if $reportState.loading}
  <div class="page status-message"><h1>Checking today…</h1></div>
{:else if $reportState.error}
  <div class="page status-message"><p>{$reportState.error}</p></div>
{:else if $reportState.dashboard}
  {@const dashboard = $reportState.dashboard}
  {@const report = dashboard.report}
  <div class="page today-page">
    <div class="mobile-only">
      <BusinessHeader business={dashboard.business.name} subtitle="Today" />
      <hr class="section-rule" />
    </div>
    <header class="page-header desktop-only">
      <div><h1>Today</h1><p class="muted">Daily operating report</p></div>
    </header>

    <section class="daily-unavailable card">
      <span class="status-dot"></span>
      <div>
        <h2>The daily POS feed isn’t connected yet.</h2>
        <p>
          Larry won’t turn monthly evidence into a daily conclusion. The latest reconciled month is
          ready below while the daily integration is added.
        </p>
      </div>
    </section>

    <section class="month-glance">
      <p class="eyebrow">Latest verified report · {monthLabel(report.period)}</p>
      <h1>{report.headline.change < 0 ? 'Profit needs attention.' : 'Profit moved in the right direction.'}</h1>
      <div class="glance-grid">
        <div><span>Profit change</span><strong class:negative={report.headline.change < 0} class:positive={report.headline.change > 0}>{money(report.headline.change, true)}</strong></div>
        <div><span>Questions</span><strong>{report.questions.length}</strong></div>
        <div><span>Worth checking</span><strong>{report.verify.length}</strong></div>
      </div>
    </section>

    {#if report.findings.length}
      <section>
        <h2>What stands out this month</h2>
        <div class="signals">
          {#each report.findings.slice(0, 3) as finding}
            <a href="/month">
              <span>{driverLabel(finding.leaf)}</span>
              <strong class:negative={finding.attribution_dollars < 0} class:positive={finding.attribution_dollars > 0}>{money(finding.attribution_dollars, true)}</strong>
            </a>
          {/each}
        </div>
      </section>
    {/if}

    {#if report.observability}
      {@const prism = report.observability}
      <section class="prism-card" aria-label="PRISM observability snapshot">
        <div class="prism-head">
          <div><p class="eyebrow">{prism.provider} observability</p><h2>{prism.agent_name}</h2></div>
          <span>{prism.model}</span>
        </div>
        <div class="prism-grid">
          <div><span>Live traces</span><strong>{prism.live_traces}</strong></div>
          <div><span>Active agents</span><strong>{prism.active_agents}</strong></div>
          <div><span>Average latency</span><strong>{prism.average_latency_seconds}s</strong></div>
          <div><span>Guardrail blocks</span><strong>{prism.guardrail_blocks}</strong></div>
          <div><span>Compliance</span><strong>{prism.compliance_score_pct}%</strong></div>
          <div><span>Cost today</span><strong>${prism.cost_today.toFixed(3)}</strong></div>
        </div>
        <p class="snapshot-note">Snapshot captured {prism.captured_at}. Financial figures above remain sourced only from the imported CSV.</p>
      </section>
    {/if}
  </div>
{/if}

<style>
  .today-page { width: min(100%, 62rem); }
  .daily-unavailable { display: flex; gap: 1rem; margin-bottom: 3rem; border-color: var(--amber); }
  .daily-unavailable h2 { margin-bottom: 0.3rem; }
  .daily-unavailable p { margin-bottom: 0; color: var(--muted); }
  .status-dot { width: 0.8rem; height: 0.8rem; flex: 0 0 auto; margin-top: 0.35rem; border-radius: 50%; background: var(--amber); }
  .month-glance { margin-bottom: 2.5rem; }
  .month-glance > h1 { max-width: 20ch; }
  .glance-grid { display: grid; grid-template-columns: repeat(3, 1fr); border: 1px solid var(--line); }
  .glance-grid div { display: grid; gap: 0.25rem; border-right: 1px solid var(--line); padding: 1rem; }
  .glance-grid div:last-child { border: 0; }
  .glance-grid span { color: var(--muted); }
  .glance-grid strong { font-family: var(--font-mono); font-size: 1.25rem; }
  .signals { border-top: 1px solid var(--line); }
  .signals a { display: flex; justify-content: space-between; gap: 1rem; border-bottom: 1px solid var(--line); padding: 0.8rem 0; }
  .signals strong { font-family: var(--font-mono); }
  .prism-card { margin-top: 2.75rem; border: 1px solid var(--line); border-radius: 0.7rem; background: var(--white); overflow: hidden; }
  .prism-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; border-bottom: 1px solid var(--line); padding: 1rem 1.1rem; }
  .prism-head h2, .prism-head p { margin: 0; }
  .prism-head > span { border: 1px solid var(--line); border-radius: 999px; padding: 0.3rem 0.65rem; color: var(--muted); font-family: var(--font-mono); font-size: 0.75rem; }
  .prism-grid { display: grid; grid-template-columns: repeat(3, 1fr); }
  .prism-grid div { display: grid; gap: 0.25rem; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); padding: 1rem 1.1rem; }
  .prism-grid div:nth-child(3n) { border-right: 0; }
  .prism-grid span, .snapshot-note { color: var(--muted); }
  .prism-grid strong { font-family: var(--font-mono); font-size: 1.1rem; }
  .snapshot-note { margin: 0; padding: 0.75rem 1.1rem; font-size: 0.78rem; }
  @media (max-width: 47.99rem) {
    .today-page { padding-top: 1.4rem; }
    .glance-grid { grid-template-columns: 1fr; }
    .glance-grid div { border-right: 0; border-bottom: 1px solid var(--line); }
    .prism-grid { grid-template-columns: 1fr 1fr; }
    .prism-grid div, .prism-grid div:nth-child(3n) { border-right: 1px solid var(--line); }
    .prism-grid div:nth-child(2n) { border-right: 0; }
  }
</style>
