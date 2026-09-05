<script lang="ts">
  import { driverLabel, money, percent } from '$lib/format';
  import type { Dashboard, SheetRow } from '$lib/types';

  let { dashboard }: { dashboard: Dashboard } = $props();

  let selected = $state<SheetRow | null>(null);
  let showInsight = $state(true);
  const report = $derived(dashboard.report);
  const maxImpact = $derived(
    Math.max(...dashboard.sheet_rows.map((item) => Math.abs(item.change || 0)), 1)
  );

  $effect(() => {
    if (!selected && dashboard.sheet_rows.length) {
      selected = dashboard.sheet_rows.find((row) => row.kind === 'cause') || dashboard.sheet_rows[0];
    }
  });

  function findingFor(key: string) {
    return report.findings.find((finding) => finding.leaf === key);
  }

  function choose(row: SheetRow) {
    selected = row;
    showInsight = true;
  }

  function askLarry() {
    if (!selected) return;
    window.dispatchEvent(
      new CustomEvent('larry:open', {
        detail: { prompt: `Explain ${driverLabel(selected.key).toLowerCase()} from this workbook.` }
      })
    );
  }
</script>

<section class="workbook" aria-label={`Workbook analysis for ${report.period}`}>
  <div class="workbook-bar">
    <div class="file-state"><span class="sheet-icon">▦</span><strong>August analysis</strong><span>Saved</span></div>
    <div class="sheet-tools" aria-label="Workbook tools">
      <button aria-label="Undo" title="Undo">↶</button>
      <button aria-label="Redo" title="Redo">↷</button>
      <span></span>
      <button title="Format as currency">$</button>
      <button title="Percent format">%</button>
      <button title="More options">•••</button>
    </div>
  </div>

  <div class="formula-bar">
    <span class="name-box">{selected ? `${selected.kind === 'metric' ? 'B' : 'D'}${dashboard.sheet_rows.indexOf(selected) + 2}` : 'A1'}</span>
    <strong>fx</strong>
    {#if selected}
      <span>
        {driverLabel(selected.label)}
        {#if selected.change !== null} · period effect <b class="mono">{money(selected.change, true)}</b>{/if}
        · {selected.note}
      </span>
      {#if selected.node}<a href="/audit">Trace →</a>{/if}
    {:else}
      <span>Select a cell to inspect its source.</span>
    {/if}
  </div>

  <div class="grid-wrap">
    <table>
      <thead>
        <tr class="letters"><th></th><th>A</th><th>B</th><th>C</th><th>D</th><th>E</th><th>F</th></tr>
        <tr><th></th><th>Account / driver</th><th>Prior period</th><th>August</th><th>Change</th><th>Confidence</th><th>What Larry noticed</th></tr>
      </thead>
      <tbody>
        {#each dashboard.sheet_rows as row, index}
          <tr
            class:selected={selected?.key === row.key}
            class:cause-row={row.kind === 'cause'}
            tabindex="0"
            onclick={() => choose(row)}
            onkeydown={(event) => event.key === 'Enter' && choose(row)}
          >
            <td class="row-number">{index + 1}</td>
            <th>
              {#if row.kind === 'cause'}
                <span
                  class="dot"
                  class:positive-dot={(row.change || 0) > 0}
                  style={`--dot:${Math.max(0.32, Math.abs(row.change || 0) / maxImpact)}rem`}
                ></span>
              {/if}
              {driverLabel(row.label)}
            </th>
            <td class="number-cell">{row.prior === null ? '' : money(row.prior)}</td>
            <td class="number-cell">{row.current === null ? '' : money(row.current)}</td>
            <td class:negative={(row.change || 0) < 0} class:positive={(row.change || 0) > 0} class="number-cell">
              {row.change === null ? '' : money(row.change, true)}
            </td>
            <td>{row.confidence === null ? '' : row.confidence === 1 ? 'Computed' : percent(row.confidence * 100)}</td>
            <td>{row.note}</td>
          </tr>
        {/each}
        {#each Array(Math.max(5, 13 - dashboard.sheet_rows.length)) as _, extra}
          <tr class="blank"><td class="row-number">{dashboard.sheet_rows.length + extra + 1}</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
        {/each}
      </tbody>
    </table>

    {#if selected && selected.kind === 'cause' && showInsight}
      {@const finding = findingFor(selected.key)}
      <aside class="larry-popover">
        <button class="close" onclick={() => (showInsight = false)} aria-label="Dismiss Larry insight">×</button>
        <span class="larry-label">✦ Larry noticed</span>
        <strong>{driverLabel(selected.label)} moved profit {money(selected.change || 0, true)}</strong>
        <p>{finding?.hypotheses?.[0]?.claim || selected.note}</p>
        <div><button onclick={askLarry}>Ask Larry</button><a href="/audit">View source</a></div>
      </aside>
    {/if}
  </div>

  <nav class="sheet-tabs" aria-label="Workbook sheets">
    <a class="active" href="/month">P&amp;L</a>
    <a href="/month">Causes</a>
    <a href="/sandbox">Assumptions</a>
    <a href="/audit">Audit trail</a>
    <button aria-label="Add sheet">＋</button>
  </nav>
</section>

<style>
  .workbook { min-width: 0; border: 1px solid var(--line); background: var(--white); box-shadow: 0 1px 2px color-mix(in srgb, var(--chalk) 5%, transparent); }
  .workbook-bar { display: flex; align-items: center; justify-content: space-between; min-height: 2.9rem; border-bottom: 1px solid var(--line); padding: 0.35rem 0.65rem; }
  .file-state, .sheet-tools { display: flex; align-items: center; gap: 0.55rem; }
  .file-state > span:last-child { color: var(--muted); font-size: 0.78rem; }
  .sheet-icon { display: grid; width: 1.7rem; height: 1.7rem; place-items: center; border-radius: 0.25rem; background: var(--stonks); color: white; }
  .sheet-tools button { min-width: 2rem; min-height: 2rem; border: 0; padding: 0.2rem; color: var(--muted); }
  .sheet-tools span { width: 1px; height: 1.4rem; background: var(--line); }
  .formula-bar { display: grid; grid-template-columns: 4.5rem auto 1fr auto; align-items: center; min-height: 2.8rem; border-bottom: 1px solid var(--line); font-size: 0.85rem; }
  .formula-bar > * { padding: 0.35rem 0.65rem; }
  .name-box { align-self: stretch; display: grid; place-items: center; border-right: 1px solid var(--line); color: var(--muted); font-family: var(--font-mono); }
  .formula-bar > strong { color: var(--muted); }
  .formula-bar a { color: var(--awning); font-weight: 700; }
  .grid-wrap { position: relative; overflow: auto; }
  table { width: 100%; min-width: 68rem; border-collapse: collapse; table-layout: fixed; font-size: 0.88rem; }
  th, td { height: 2.45rem; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); padding: 0.4rem 0.65rem; text-align: left; }
  thead { background: var(--soft); }
  thead th:first-child, .row-number { width: 2.7rem; color: var(--muted); text-align: center; font-family: var(--font-mono); font-weight: 400; }
  thead th:nth-child(2) { width: 21%; }
  thead th:nth-child(3), thead th:nth-child(4), thead th:nth-child(5) { width: 12%; }
  thead th:nth-child(6) { width: 11%; }
  .letters th { height: 1.65rem; padding: 0.1rem; text-align: center; color: var(--muted); font-family: var(--font-mono); font-weight: 400; }
  tbody th { font-weight: 500; }
  tbody tr { cursor: cell; }
  tbody tr:hover > *, tbody tr.selected > * { background: color-mix(in srgb, var(--awning) 6%, var(--white)); }
  tbody tr.selected > * { box-shadow: inset 0 1px var(--awning), inset 0 -1px var(--awning); }
  tbody tr.cause-row th { padding-left: 1.5rem; }
  .number-cell { text-align: right; font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
  .dot { display: inline-block; width: calc(var(--dot) + 0.25rem); height: calc(var(--dot) + 0.25rem); max-width: 0.75rem; max-height: 0.75rem; margin-right: 0.4rem; border-radius: 50%; background: var(--tomato); vertical-align: -0.02rem; }
  .positive-dot { background: var(--stonks); }
  .blank td { color: transparent; }
  .larry-popover { position: absolute; top: 5.4rem; right: 1rem; z-index: 5; width: 18rem; border: 1px solid var(--line); border-radius: 0.55rem; background: var(--white); padding: 0.85rem; box-shadow: 0 0.6rem 2rem color-mix(in srgb, var(--chalk) 13%, transparent); }
  .larry-label { display: block; margin-bottom: 0.35rem; color: var(--awning); font-size: 0.78rem; font-weight: 700; }
  .larry-popover p { margin: 0.35rem 0 0.7rem; color: var(--muted); }
  .larry-popover div { display: flex; align-items: center; gap: 0.75rem; }
  .larry-popover div button { min-height: 2rem; border-color: var(--awning); padding: 0.25rem 0.6rem; color: var(--awning); }
  .larry-popover a { color: var(--muted); font-size: 0.82rem; }
  .close { position: absolute; top: 0.35rem; right: 0.35rem; width: 1.8rem; min-height: 1.8rem; border: 0; padding: 0; color: var(--muted); }
  .sheet-tabs { display: flex; align-items: center; min-height: 2.5rem; overflow-x: auto; background: var(--soft); padding-left: 0.4rem; }
  .sheet-tabs a { min-width: 6rem; border-right: 1px solid var(--line); padding: 0.45rem 0.8rem; text-align: center; white-space: nowrap; }
  .sheet-tabs a.active { border-top: 2px solid var(--stonks); background: var(--white); font-weight: 700; }
  .sheet-tabs button { min-height: 2rem; border: 0; padding: 0.2rem 0.7rem; color: var(--muted); }
</style>
