<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import type { Conversation as ConversationInstance } from '@elevenlabs/client';
  import { createVoiceSession } from '$lib/api/client';
  import { loadDashboard, reportState } from '$lib/api/report';
  import BusinessHeader from '$lib/components/BusinessHeader.svelte';
  import { monthLabel } from '$lib/format';

  type Message = { role: 'user' | 'agent'; text: string };
  let session = $state<ConversationInstance | null>(null);
  let status = $state<'idle' | 'connecting' | 'connected'>('idle');
  let mode = $state<'listening' | 'speaking'>('listening');
  let messages = $state<Message[]>([]);
  let typed = $state('');
  let error = $state<string | null>(null);

  onMount(() => loadDashboard());
  onDestroy(() => session?.endSession());

  async function start() {
    const dashboard = $reportState.dashboard;
    if (!dashboard || status !== 'idle') return;
    status = 'connecting';
    error = null;
    try {
      const { Conversation } = await import('@elevenlabs/client');
      const config = await createVoiceSession(dashboard.report.run_id);
      session = await Conversation.startSession({
        signedUrl: config.signed_url,
        dynamicVariables: config.dynamic_variables,
        onConnect: () => (status = 'connected'),
        onDisconnect: () => {
          status = 'idle';
          session = null;
        },
        onModeChange: ({ mode: nextMode }) => (mode = nextMode),
        onMessage: ({ role, message }) => {
          messages = [...messages, { role, text: message }];
        },
        onError: (message) => {
          error = message;
          status = 'idle';
        }
      });
    } catch (cause) {
      error = cause instanceof Error ? cause.message : 'Could not start the analyst.';
      status = 'idle';
    }
  }

  async function stop() {
    await session?.endSession();
    session = null;
    status = 'idle';
  }

  function send() {
    const value = typed.trim();
    if (!value || !session) return;
    session.sendUserMessage(value);
    messages = [...messages, { role: 'user', text: value }];
    typed = '';
  }
</script>

{#if $reportState.loading}
  <div class="page status-message"><h1>Preparing the analyst…</h1></div>
{:else if $reportState.error}
  <div class="page status-message"><p>{$reportState.error}</p></div>
{:else if $reportState.dashboard}
  {@const dashboard = $reportState.dashboard}
  <div class="page ask-page">
    <div class="mobile-only">
      <BusinessHeader business={dashboard.business.name} subtitle={`Ask about ${monthLabel(dashboard.report.period).split(' ')[0]}`} />
      <hr class="section-rule" />
    </div>
    <header class="page-header desktop-only">
      <div><h1>Ask the analyst</h1><p class="muted">Every figure comes from the current verified run.</p></div>
    </header>

    <div class="voice-state">
      <button
        class:active={status === 'connected'}
        class:speaking={mode === 'speaking'}
        disabled={status === 'connecting'}
        onclick={status === 'idle' ? start : stop}
        aria-label={status === 'idle' ? 'Start voice conversation' : 'Stop voice conversation'}
      >
        {status === 'connecting' ? 'Connecting' : status === 'idle' ? 'Start' : mode === 'speaking' ? 'Speaking' : 'Listening'}
      </button>
      {#if status === 'idle'}<p>Tap to talk with the analyst.</p>{/if}
    </div>

    <div class="transcript" aria-live="polite">
      {#each messages as message}
        <article class:agent={message.role === 'agent'}>
          <span>{message.role === 'agent' ? 'Analyst' : 'You'}</span>
          <p>{message.text}</p>
        </article>
      {:else}
        <p class="muted">Ask what changed, what to fix first, or what an amount assumes.</p>
      {/each}
    </div>

    {#if error}<p class="negative voice-error">{error}</p>{/if}

    <form onsubmit={(event) => { event.preventDefault(); send(); }}>
      <label for="question">Type a question</label>
      <input id="question" bind:value={typed} placeholder="Or type here" disabled={!session} />
      <button type="submit" disabled={!session || !typed.trim()}>Send</button>
      {#if session}<button type="button" onclick={stop}>Stop</button>{/if}
    </form>
  </div>
{/if}

<style>
  .ask-page { display: flex; width: min(100%, 54rem); min-height: 100vh; flex-direction: column; }
  .voice-state { display: grid; justify-items: center; margin: 3rem 0; }
  .voice-state > button { width: 9.5rem; height: 9.5rem; border: 0; border-radius: 50%; background: color-mix(in srgb, var(--awning) 18%, transparent); box-shadow: inset 0 0 0 1.4rem color-mix(in srgb, var(--awning) 22%, transparent); color: var(--awning); }
  .voice-state > button.active { background: var(--awning); box-shadow: 0 0 0 1.25rem color-mix(in srgb, var(--awning) 18%, transparent); color: white; }
  .voice-state > button.speaking { box-shadow: 0 0 0 1.5rem color-mix(in srgb, var(--stonks) 20%, transparent); }
  .voice-state p { margin: 1.5rem 0 0; color: var(--muted); }
  .transcript { flex: 1; min-height: 15rem; }
  .transcript article { margin: 1rem 0; }
  .transcript article span { color: var(--muted); font-size: 0.85rem; }
  .transcript article p { max-width: 40rem; margin: 0.3rem 0 0; font-size: 1.2rem; }
  .transcript article.agent { border-left: 4px solid var(--awning); padding-left: 0.8rem; }
  .voice-error { text-align: center; }
  form { display: grid; grid-template-columns: 1fr auto auto; gap: 0.6rem; margin-top: auto; padding-top: 1rem; }
  form label { position: absolute; width: 1px; height: 1px; clip-path: inset(50%); }
  form input { min-width: 0; min-height: 3rem; border: 1px solid var(--chalk); border-radius: 0.6rem; background: var(--white); padding: 0.65rem 0.9rem; color: var(--chalk); }
  @media (max-width: 47.99rem) {
    .ask-page { padding-top: 1.4rem; }
    .voice-state { margin: 3.5rem 0; }
    .transcript { min-height: 12rem; }
    form { position: sticky; bottom: 4.2rem; background: var(--paper); padding-bottom: 0.5rem; }
    form button[type='submit'] { display: none; }
  }
</style>
