<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import type { Conversation as ConversationInstance } from '@elevenlabs/client';
  import { askWorkbook, createVoiceSession } from '$lib/api/client';
  import { reportState } from '$lib/api/report';
  import type { ChatTurn } from '$lib/types';

  type VisibleTurn = ChatTurn & { sources?: string[] };

  let open = $state(false);
  let full = $state(false);
  let draft = $state('');
  let sending = $state(false);
  let error = $state<string | null>(null);
  let turns = $state<VisibleTurn[]>([]);
  let conversation = $state<ConversationInstance | null>(null);
  let voiceStatus = $state<'idle' | 'connecting' | 'listening' | 'speaking'>('idle');

  onDestroy(() => conversation?.endSession());
  onMount(() => {
    const openFromCell = (event: Event) => {
      const prompt = (event as CustomEvent<{ prompt?: string }>).detail?.prompt;
      if (prompt) draft = prompt;
      open = true;
    };
    window.addEventListener('larry:open', openFromCell);
    return () => window.removeEventListener('larry:open', openFromCell);
  });

  async function send() {
    const question = draft.trim();
    const dashboard = $reportState.dashboard;
    if (!question || !dashboard || sending) return;
    open = true;
    const history = turns.map(({ role, text }) => ({ role, text }));
    turns = [...turns, { role: 'user', text: question }];
    draft = '';
    sending = true;
    error = null;
    try {
      const reply = await askWorkbook(dashboard.report.run_id, question, history);
      turns = [
        ...turns,
        { role: 'assistant', text: reply.answer, sources: reply.sources }
      ];
    } catch (cause) {
      error = cause instanceof Error ? cause.message : 'The analyst could not answer.';
    } finally {
      sending = false;
    }
  }

  async function toggleVoice() {
    const dashboard = $reportState.dashboard;
    if (conversation) {
      await conversation.endSession();
      conversation = null;
      voiceStatus = 'idle';
      return;
    }
    if (!dashboard || voiceStatus !== 'idle') return;
    voiceStatus = 'connecting';
    error = null;
    try {
      const { Conversation } = await import('@elevenlabs/client');
      const config = await createVoiceSession(dashboard.report.run_id);
      conversation = await Conversation.startSession({
        signedUrl: config.signed_url,
        dynamicVariables: config.dynamic_variables,
        onConnect: () => (voiceStatus = 'listening'),
        onDisconnect: () => {
          voiceStatus = 'idle';
          conversation = null;
        },
        onModeChange: ({ mode }) => (voiceStatus = mode),
        onMessage: ({ role, message }) => {
          turns = [
            ...turns,
            { role: role === 'agent' ? 'assistant' : 'user', text: message }
          ];
        },
        onError: (message) => {
          error = message;
          voiceStatus = 'idle';
        }
      });
    } catch (cause) {
      error = cause instanceof Error ? cause.message : 'Voice could not start.';
      voiceStatus = 'idle';
    }
  }
</script>

{#if !open}
  <button class="larry-launcher" onclick={() => (open = true)} aria-label="Open Larry assistant">
    <span>✦</span>
  </button>
{:else}
<aside id="analyst-dock" class:full aria-label="Chat with Larry">
    <header>
      <div>
        <h2><span class="spark" aria-hidden="true">✦</span> Larry</h2>
        <p>Answers are grounded in the imported workbook.</p>
      </div>
      <div class="panel-actions">
        <button
          class="voice"
          class:active={voiceStatus !== 'idle'}
          onclick={toggleVoice}
          disabled={!$reportState.dashboard || voiceStatus === 'connecting'}
          aria-label={voiceStatus === 'idle' ? 'Start voice conversation' : 'Stop voice conversation'}
        >
          <span class="voice-orb" aria-hidden="true">
            <i></i><i></i><i></i><i></i>
          </span>
          <span class="voice-copy">
            <strong>{voiceStatus === 'idle' ? 'Talk' : voiceStatus === 'connecting' ? 'Connecting' : voiceStatus}</strong>
            <small>ElevenLabs</small>
          </span>
        </button>
        <button
          class="expand"
          onclick={() => (full = !full)}
          aria-label={full ? 'Exit full screen chat' : 'Full screen chat'}
          aria-expanded={full}
        >{full ? '↙' : '↗'}</button>
        <button class="expand" onclick={() => { open = false; full = false; }} aria-label="Close Larry">×</button>
      </div>
    </header>

    <div class="messages" aria-live="polite">
      {#each turns as turn}
        <article class:assistant={turn.role === 'assistant'}>
          <span>{turn.role === 'assistant' ? 'Analyst' : 'You'}</span>
          <p>{turn.text}</p>
          {#if turn.sources?.length}
            <small>From {turn.sources.join(' · ')}</small>
          {/if}
        </article>
      {:else}
        <div class="empty">
          <strong>Try asking</strong>
          <button onclick={() => (draft = 'What changed profit this month?')}>What changed profit?</button>
          <button onclick={() => (draft = 'What should I do first?')}>What should I do first?</button>
          <button onclick={() => (draft = 'What should I verify?')}>What should I verify?</button>
        </div>
      {/each}
      {#if sending}<p class="thinking">Reading the workbook…</p>{/if}
    </div>

    {#if error}<p class="error">{error}</p>{/if}

    <form onsubmit={(event) => { event.preventDefault(); send(); }}>
      <label for="analyst-question">Ask about the workbook</label>
      <textarea
        id="analyst-question"
        bind:value={draft}
        rows={full ? 3 : 1}
        placeholder="Ask about sales, costs, causes, or next steps"
        onkeydown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            send();
          }
        }}
      ></textarea>
      <button class="send" type="submit" disabled={!draft.trim() || sending || !$reportState.dashboard}>Send</button>
    </form>
</aside>
{/if}

<style>
  .larry-launcher {
    position: fixed;
    right: 1.4rem;
    bottom: 1.4rem;
    z-index: 70;
    display: grid;
    width: 3.5rem;
    min-height: 3.5rem;
    place-items: center;
    border: 0;
    border-radius: 50%;
    background: var(--chalk);
    color: white;
    box-shadow: 0 0.55rem 1.5rem color-mix(in srgb, var(--chalk) 20%, transparent);
  }

  .larry-launcher span {
    color: #8aa9ff;
    font-size: 1.4rem;
  }

  aside {
    position: fixed;
    right: 1.25rem;
    bottom: 1.25rem;
    z-index: 70;
    display: grid;
    grid-template-rows: auto 1fr auto auto;
    width: 24rem;
    height: 32rem;
    overflow: hidden;
    border: 1px solid var(--line);
    border-radius: 0.625rem;
    background: var(--white);
    box-shadow: 0 0.65rem 2rem color-mix(in srgb, var(--chalk) 14%, transparent);
    transition: width 180ms ease, height 180ms ease, inset 180ms ease;
  }

  aside.full {
    inset: 2rem auto 2rem 50%;
    width: min(72rem, calc(100vw - 4rem));
    height: auto;
    transform: translateX(-50%);
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    border-bottom: 1px solid var(--line);
    padding: 1rem;
  }

  h2,
  header p {
    margin: 0;
  }

  .spark {
    color: var(--awning);
  }

  .panel-actions {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  header p {
    color: var(--muted);
    font-size: 0.82rem;
  }

  .voice {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    min-height: 2.5rem;
    border: 0;
    border-radius: 999px;
    background: #111;
    padding: 0.25rem 0.7rem 0.25rem 0.25rem;
    color: white;
    box-shadow: inset 0 0 0 1px color-mix(in srgb, white 12%, transparent);
  }

  .voice:hover:not(:disabled) {
    border-color: transparent;
    background: #252525;
    box-shadow: inset 0 0 0 1px color-mix(in srgb, white 18%, transparent),
      0 0.2rem 0.65rem color-mix(in srgb, black 15%, transparent);
  }

  .voice.active {
    background: #111;
  }

  .voice-orb {
    display: flex;
    width: 2rem;
    height: 2rem;
    align-items: center;
    justify-content: center;
    gap: 0.13rem;
    border-radius: 50%;
    background: linear-gradient(145deg, #fff 10%, #d8d8d8 88%);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, black 8%, transparent);
  }

  .voice-orb i {
    width: 0.13rem;
    height: 0.55rem;
    border-radius: 99px;
    background: #111;
  }

  .voice-orb i:nth-child(2) { height: 0.9rem; }
  .voice-orb i:nth-child(3) { height: 0.7rem; }
  .voice-orb i:nth-child(4) { height: 0.4rem; }

  .voice.active .voice-orb {
    animation: voice-pulse 1.6s ease-in-out infinite;
    background: radial-gradient(circle at 35% 30%, #fff 0 8%, #dce6ff 42%, #91adff 100%);
  }

  .voice.active .voice-orb i {
    animation: voice-bars 0.8s ease-in-out infinite alternate;
  }

  .voice.active .voice-orb i:nth-child(2) { animation-delay: -0.22s; }
  .voice.active .voice-orb i:nth-child(3) { animation-delay: -0.44s; }
  .voice.active .voice-orb i:nth-child(4) { animation-delay: -0.12s; }

  .voice-copy {
    display: grid;
    line-height: 1.05;
    text-align: left;
  }

  .voice-copy strong {
    font-size: 0.78rem;
    font-weight: 650;
    text-transform: capitalize;
  }

  .voice-copy small {
    color: #bdbdbd;
    font-size: 0.62rem;
    letter-spacing: 0.01em;
  }

  .expand {
    width: 2.35rem;
    min-height: 2.35rem;
    padding: 0;
    border-color: var(--line);
    color: var(--muted);
    font-size: 1.15rem;
  }

  .messages {
    overflow-y: auto;
    padding: 1rem;
  }

  article {
    margin: 0 0 1rem 2rem;
    border-radius: 0.625rem;
    background: var(--soft);
    padding: 0.75rem 0.9rem;
  }

  article.assistant {
    margin-right: 1.5rem;
    margin-left: 0;
    border-left: 3px solid var(--awning);
    background: var(--white);
  }

  article > span,
  article small {
    display: block;
    color: var(--muted);
    font-size: 0.75rem;
  }

  article p {
    margin: 0.25rem 0;
  }

  article small {
    font-family: var(--font-mono);
  }

  .empty {
    display: grid;
    align-content: center;
    gap: 0.55rem;
    min-height: 100%;
    text-align: center;
  }

  .empty button {
    min-height: 2.2rem;
    background: var(--white);
  }

  .thinking {
    color: var(--muted);
  }

  .error {
    margin: 0;
    border-top: 1px solid var(--line);
    padding: 0.65rem 1rem;
    color: var(--tomato);
    font-size: 0.85rem;
  }

  form {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.6rem;
    border-top: 1px solid var(--line);
    background: var(--white);
    padding: 0.8rem;
  }

  form label {
    position: absolute;
    width: 1px;
    height: 1px;
    clip-path: inset(50%);
  }

  textarea {
    min-width: 0;
    resize: none;
    border: 1px solid var(--line);
    border-radius: 0.4rem;
    background: var(--paper);
    padding: 0.55rem 0.65rem;
    color: var(--chalk);
  }

  .send {
    align-self: stretch;
    border-color: var(--awning);
    background: var(--awning);
    color: white;
  }

  @keyframes voice-pulse {
    50% { box-shadow: 0 0 0 0.28rem color-mix(in srgb, #91adff 22%, transparent); }
  }

  @keyframes voice-bars {
    to { transform: scaleY(0.55); }
  }

</style>
