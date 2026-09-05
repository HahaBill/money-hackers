<script lang="ts">
  import { driverLabel, findingSentence, headlineCopy, money, percent } from '$lib/format';
  import type { Dashboard, Finding } from '$lib/types';

  let {
    dashboard,
    onselect
  }: { dashboard: Dashboard; onselect: (finding: Finding) => void } = $props();

  const report = $derived(dashboard.report);
  const currentProfit = $derived(
    typeof dashboard.metrics.curr_profit === 'number' ? dashboard.metrics.curr_profit : null
  );
  const revenue = $derived(
    typeof dashboard.metrics.revenue === 'number' ? dashboard.metrics.revenue : null
  );
  const recommendation = $derived(report.simulations?.[0]);

  function findingFor(driver: string) {
    return report.findings.find((finding) => finding.leaf === driver);
  }
</script>

<article class="receipt" aria-label={`Analysis receipt for ${report.period}`}>
  <h1>{headlineCopy(report.headline.change)}</h1>

  {#if revenue !== null}
    <div class="metric">
      <span>Sales</span>
      <strong>{money(revenue)}</strong>
    </div>
  {/if}
  {#if currentProfit !== null}
    <div class="metric primary-metric">
      <span>Profit</span>
      <strong>{money(currentProfit)}</strong>
    </div>
  {/if}
  <div class="comparison">
    <span>vs prior period</span>
    <strong class:negative={report.headline.change < 0} class:positive={report.headline.change > 0}>
      {money(report.headline.change, true)}
      {report.headline.change < 0 ? '↓' : '↑'}
    </strong>
  </div>
  {#if report.headline.change_pct !== undefined}
    <div class="comparison">
      <span>profit change</span>
      <strong class:negative={report.headline.change_pct < 0} class:positive={report.headline.change_pct > 0}>
        {percent(report.headline.change_pct, true)}
      </strong>
    </div>
  {/if}

  <hr class="section-rule" />
  <h2>What changed</h2>
  <div class="causes">
    {#each dashboard.attribution_summary as attribution}
      {@const finding = findingFor(attribution.driver)}
      {#if finding}
        <button class="cause" onclick={() => onselect(finding)}>
          <span>{findingSentence(attribution.driver, attribution.dollars)}</span>
          <strong class:negative={attribution.dollars < 0} class:positive={attribution.dollars > 0}>
            {money(attribution.dollars, true)}
          </strong>
        </button>
      {:else}
        <div class="cause static">
          <span>{driverLabel(attribution.driver)}</span>
          <strong class:negative={attribution.dollars < 0} class:positive={attribution.dollars > 0}>
            {money(attribution.dollars, true)}
          </strong>
        </div>
      {/if}
    {/each}
  </div>
  <div class="total">
    <span>Total profit change</span>
    <strong>{money(dashboard.attribution_total, true)}</strong>
  </div>

  {#if recommendation}
    <hr class="section-rule" />
    <h2>Do first</h2>
    <p class="recommendation">
      Move {driverLabel(recommendation.leaf).toLowerCase()} {Math.abs(recommendation.delta_pct)}%.
      It models to <strong class="positive">{money(recommendation.delta_profit, true)} a month</strong>,
      {recommendation.assumption}.
    </p>
    <div class="actions">
      <a class="primary-button" href="/ask">Hear it</a>
      <a class="secondary-button" href="/sandbox">Show me</a>
    </div>
  {/if}

  <hr class="section-rule" />
  <a class="queue-link" href="/queue">
    <span>Worth checking</span><strong>{report.verify?.length || 0} ›</strong>
  </a>
  <a class="queue-link" href="/queue">
    <span>Questions for you</span><strong>{report.questions?.length || 0} ›</strong>
  </a>

  <hr class="section-rule" />
  <p class="trust-line">
    Reconciliation {report.reconciliation}. Every displayed amount links to run
    <span class="mono">{report.run_id}</span>.
  </p>
</article>

<style>
  .receipt {
    width: min(100%, 27rem);
    margin: 0 auto;
  }

  h1 {
    max-width: 22ch;
    margin: 1.8rem 0;
    font-size: 1.75rem;
  }

  h2 {
    margin-bottom: 0.85rem;
    font-size: 1.1rem;
  }

  .metric,
  .comparison,
  .cause,
  .total,
  .queue-link {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
  }

  .metric {
    margin-top: 0.85rem;
    font-size: 1.2rem;
  }

  .metric strong,
  .comparison strong,
  .cause strong,
  .total strong,
  .queue-link strong {
    flex: 0 0 auto;
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }

  .primary-metric {
    margin-top: 1.5rem;
  }

  .comparison {
    color: var(--muted);
    font-size: 0.95rem;
  }

  .causes {
    display: grid;
    gap: 0.1rem;
  }

  .cause {
    width: 100%;
    min-height: 2.35rem;
    border: 0;
    padding: 0;
    text-align: left;
  }

  button.cause:hover span {
    color: var(--awning);
  }

  .cause.static {
    padding: 0.35rem 0;
  }

  .total {
    margin-top: 0.55rem;
    border-top: 1px solid var(--chalk);
    padding-top: 0.5rem;
    font-weight: 700;
  }

  .recommendation {
    font-size: 1.08rem;
    line-height: 1.5;
  }

  .actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.7rem;
  }

  .primary-button,
  .secondary-button {
    display: grid;
    min-height: 2.75rem;
    place-items: center;
    border: 1.5px solid var(--awning);
    border-radius: 0.55rem;
  }

  .primary-button {
    background: var(--awning);
    color: white;
  }

  .secondary-button {
    border-color: var(--chalk);
  }

  .queue-link {
    min-height: 2.4rem;
  }

  .queue-link:hover span {
    color: var(--awning);
  }

  .trust-line {
    color: var(--muted);
    font-size: 0.85rem;
  }
</style>
