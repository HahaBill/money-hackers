<script lang="ts">
  import { rateFinding } from '$lib/api/client';
  import { driverLabel, findingSentence, money, percent } from '$lib/format';
  import type { Dashboard, Finding } from '$lib/types';

  let {
    dashboard,
    finding,
    onclose
  }: { dashboard: Dashboard; finding: Finding; onclose: () => void } = $props();

  let rating = $state<string | null>(null);
  let saving = $state(false);
  let error = $state<string | null>(null);

  const concentration = $derived(
    dashboard.report.concentrations?.find((item) => item.leaf === finding.leaf)
  );
  const lead = $derived(finding.hypotheses?.[0]);

  async function submit(next: 'right' | 'wrong' | 'incomplete') {
    saving = true;
    error = null;
    try {
      await rateFinding(dashboard.report.run_id, finding.id, lead?.id, next);
      rating = next;
    } catch (cause) {
      error = cause instanceof Error ? cause.message : 'Could not save your feedback.';
    } finally {
      saving = false;
    }
  }
</script>

<svelte:window onkeydown={(event) => event.key === 'Escape' && onclose()} />

<button class="scrim" aria-label="Close evidence" onclick={onclose}></button>
<aside aria-label="Evidence for finding" aria-live="polite">
  <header>
    <div>
      <span class="eyebrow">Why this is here</span>
      <h2>{findingSentence(finding.leaf, finding.attribution_dollars)}</h2>
    </div>
    <button class="close" aria-label="Close" onclick={onclose}>×</button>
  </header>

  <div class="impact">
    <span>Effect on profit</span>
    <strong class:negative={finding.attribution_dollars < 0} class:positive={finding.attribution_dollars > 0}>
      {money(finding.attribution_dollars, true)}
    </strong>
  </div>

  {#if concentration?.contributors?.length}
    <section>
      <h3>Mostly</h3>
      {#each concentration.contributors as contributor}
        <div class="evidence-row">
          <span>{driverLabel(contributor.entity)}</span>
          <span class="mono">{percent(contributor.share * 100)}</span>
        </div>
      {/each}
    </section>
  {/if}

  {#if lead}
    <section>
      <h3>What the evidence says</h3>
      <p>{lead.claim}</p>
      <div class="belief">
        <span>{lead.verdict}</span>
        <span class="mono">{percent(lead.posterior * 100)}</span>
      </div>
      <div class="bar" aria-label={`Confidence ${percent(lead.posterior * 100)}`}>
        <span style={`width:${Math.min(100, lead.posterior * 100)}%`}></span>
      </div>
    </section>
  {:else}
    <section>
      <h3>What the evidence says</h3>
      <p class="muted">The amount is computed, but the cause is still unresolved.</p>
    </section>
  {/if}

  <section>
    <h3>Was this explanation right?</h3>
    {#if rating}
      <p class="saved">Saved as “{rating}”. This will inform the next analysis.</p>
    {:else}
      <div class="ratings">
        <button disabled={saving} onclick={() => submit('right')}>Right</button>
        <button disabled={saving} onclick={() => submit('wrong')}>Wrong</button>
        <button disabled={saving} onclick={() => submit('incomplete')}>Incomplete</button>
      </div>
    {/if}
    {#if error}<p class="negative">{error}</p>{/if}
  </section>

  <footer>
    <span class="mono">{finding.attribution?.[0] || finding.node}</span>
    <a href="/audit">Trace in Audit →</a>
  </footer>
</aside>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 60;
    width: 100%;
    height: 100%;
    border: 0;
    border-radius: 0;
    background: color-mix(in srgb, var(--chalk) 28%, transparent);
  }

  aside {
    position: fixed;
    inset: 0 0 0 auto;
    z-index: 61;
    width: min(32rem, 92vw);
    overflow: auto;
    border-left: 1px solid var(--line);
    background: var(--paper);
    padding: 1.5rem;
    box-shadow: -1rem 0 2rem color-mix(in srgb, var(--chalk) 12%, transparent);
    animation: enter 240ms ease-out;
  }

  @keyframes enter {
    from { transform: translateX(1.5rem); opacity: 0; }
  }

  header {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    border-bottom: 1px dashed var(--line);
    padding-bottom: 1rem;
  }

  h2 {
    margin-bottom: 0;
  }

  .close {
    width: 2.75rem;
    padding: 0;
    border: 0;
    font-size: 2rem;
  }

  .impact {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin: 1.5rem 0;
  }

  .impact strong {
    font-family: var(--font-mono);
    font-size: 1.6rem;
  }

  section {
    border-top: 1px solid var(--line);
    padding: 1.25rem 0;
  }

  .evidence-row,
  .belief {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    margin: 0.35rem 0;
  }

  .belief span:first-child {
    text-transform: capitalize;
  }

  .bar {
    height: 0.45rem;
    border-radius: 0.25rem;
    background: var(--soft);
    overflow: hidden;
  }

  .bar span {
    display: block;
    height: 100%;
    background: var(--awning);
  }

  .ratings {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .saved {
    color: var(--stonks);
  }

  footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    border-top: 1px solid var(--line);
    padding-top: 1rem;
    color: var(--muted);
    font-size: 0.82rem;
  }

  footer a {
    color: var(--awning);
    font-weight: 700;
  }
</style>
