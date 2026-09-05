<script lang="ts">
  import { onMount } from 'svelte';
  import { answerQuestion } from '$lib/api/client';
  import { loadDashboard, reportState } from '$lib/api/report';
  import BusinessHeader from '$lib/components/BusinessHeader.svelte';
  import { money, monthLabel } from '$lib/format';

  let answering = $state<string | null>(null);
  let answered = $state<Record<string, string>>({});
  let errors = $state<Record<string, string>>({});
  let hiddenVerify = $state<Set<string>>(new Set());

  onMount(() => loadDashboard());

  async function choose(runId: string, questionId: string, option: string) {
    answering = questionId;
    try {
      await answerQuestion(runId, questionId, option);
      answered = { ...answered, [questionId]: option };
    } catch (cause) {
      errors = {
        ...errors,
        [questionId]: cause instanceof Error ? cause.message : 'Could not save this answer.'
      };
    } finally {
      answering = null;
    }
  }

  function dismiss(node: string) {
    hiddenVerify = new Set([...hiddenVerify, node]);
  }
</script>

{#if $reportState.loading}
  <div class="page status-message"><h1>Loading what needs you…</h1></div>
{:else if $reportState.error}
  <div class="page status-message"><div><h1>The queue isn’t reachable.</h1><p>{$reportState.error}</p></div></div>
{:else if $reportState.dashboard}
  {@const dashboard = $reportState.dashboard}
  {@const report = dashboard.report}
  {@const visibleVerify = report.verify.filter((item) => !hiddenVerify.has(item.node))}
  <div class="page queue-page">
    <div class="mobile-only">
      <BusinessHeader
        business={dashboard.business.name}
        subtitle={`${report.questions.length + visibleVerify.length} things need you`}
      />
      <hr class="section-rule" />
    </div>
    <header class="page-header desktop-only">
      <div>
        <h1>Queue</h1>
        <p class="muted">Questions and checks for {monthLabel(report.period)}</p>
      </div>
      <a class="ask" href="/ask">Ask</a>
    </header>

    {#if report.status === 'blocked'}
      <section>
        <div class="section-title"><h2>Didn’t add up</h2><span>{report.checks?.length || 1}</span></div>
        <article class="card blocked-card">
          <h3>The period could not be reconciled.</h3>
          <p>The analysis stopped before making any claims. Review the failed source checks.</p>
          {#each report.checks || [] as check}
            <p><strong>{check.label}</strong> {check.detail}</p>
          {/each}
        </article>
      </section>
    {/if}

    <section>
      <div class="section-title">
        <h2>Questions from the analyst</h2>
        <span>{report.questions.filter((question) => !answered[question.id]).length}</span>
      </div>
      {#each report.questions as question}
        <article class="card question-card">
          {#if answered[question.id]}
            <p class="saved">Noted: {answered[question.id]}. I’ll use that next period.</p>
          {:else}
            <h3>{question.text}</h3>
            {#if question.voi_dollars}
              <p class="muted">Would help resolve about {money(question.voi_dollars)}.</p>
            {/if}
            <div class="chips" aria-label="Answer choices">
              {#each question.options as option}
                <button
                  disabled={answering === question.id}
                  onclick={() => choose(report.run_id, question.id, option)}
                >{option}</button>
              {/each}
            </div>
            {#if errors[question.id]}<p class="negative">{errors[question.id]}</p>{/if}
          {/if}
        </article>
      {:else}
        <div class="empty card">No open questions. The analyst has what it needs for now.</div>
      {/each}
    </section>

    <section>
      <div class="section-title"><h2>Worth checking</h2><span>{visibleVerify.length}</span></div>
      {#each visibleVerify as item}
        <article class="card verify-card">
          <h3>{item.entity}</h3>
          <p>{item.detail || 'A recurring cost did not match the expected pattern.'}</p>
          <strong>Gap: about {money(Math.abs(item.gap_dollars))}.</strong>
          <p class="muted">{item.counter_explanation}</p>
          <div class="card-actions">
            <a class="primary-button" href="/ask">Ask about it</a>
            <button onclick={() => dismiss(item.node)}>Dismiss</button>
          </div>
        </article>
      {:else}
        <div class="empty card">Nothing needs checking in this run.</div>
      {/each}
    </section>
  </div>
{/if}

<style>
  .queue-page {
    width: min(100%, 58rem);
  }

  .ask,
  .primary-button {
    display: grid;
    min-height: 2.75rem;
    place-items: center;
    border-radius: 999px;
    background: var(--awning);
    color: white;
    padding: 0.5rem 1.2rem;
  }

  section {
    margin: 1.6rem 0;
  }

  .section-title {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 0.7rem;
  }

  .section-title h2 {
    margin: 0;
  }

  .section-title span {
    font-family: var(--font-mono);
  }

  .card + .card {
    margin-top: 0.75rem;
  }

  .question-card h3,
  .verify-card h3 {
    margin-bottom: 0.35rem;
    font-size: 1.1rem;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .chips button {
    min-height: 2.4rem;
    border: 0;
    border-radius: 999px;
    background: var(--chalk);
    color: var(--paper);
    padding: 0.4rem 0.8rem;
  }

  .saved {
    margin: 0;
    color: var(--stonks);
  }

  .verify-card > strong {
    display: block;
    margin-bottom: 0.4rem;
  }

  .card-actions {
    display: flex;
    gap: 0.65rem;
  }

  .primary-button {
    border-radius: 0.55rem;
  }

  .blocked-card {
    border-color: var(--tomato);
  }

  .empty {
    color: var(--muted);
  }

  @media (max-width: 47.99rem) {
    .queue-page {
      padding-top: 1.4rem;
    }

    .card-actions > * {
      flex: 1;
    }
  }
</style>
