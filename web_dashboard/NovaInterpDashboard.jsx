export default function NovaInterpDashboard({
  running = false,
  onStart,
  onStop,
  onRefresh,
  onToggleSettings,
  headerTags = ["Dual Channel", "Low Latency", running ? "Engine Live" : "Engine Ready"],
  scenarioControl,
  channelAControl,
  channelBControl,
  routeNodeAInput,
  routeNodeAOutput,
  routeNodeBInput,
  routeNodeBOutput,
  transcriptPaneA,
  transcriptPaneB,
  credentialsDrawer,
}) {
  return (
    <div className={`dashboard-app ${running ? "is-running" : ""}`}>
      <div className="ambient-grid" aria-hidden="true" />

      <header className="app-header">
        <div className="brand-stack">
          <div className="brand-line">
            <h1>NOVA INTERP</h1>
            <div className="status-tags">
              {headerTags.map((tag, index) => (
                <span
                  key={tag}
                  className={`tag ${
                    index === 0 ? "tag-blue" : index === 1 ? "tag-green" : "tag-muted"
                  }`}
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
          <p className="brand-copy">
            Professional bilingual interpreting console for Discord, meetings, and live sessions.
          </p>
        </div>

        <div className="header-actions">
          <div className="scenario-block">
            <span className="field-label">Scenario Template</span>
            {scenarioControl}
          </div>
          <button className="icon-button" type="button" onClick={onRefresh} aria-label="Refresh" />
          <button className="icon-button" type="button" onClick={onToggleSettings} aria-label="Settings" />
          <button className="action-button primary" type="button" onClick={onStart} disabled={running}>
            Start
          </button>
          <button className="action-button danger" type="button" onClick={onStop} disabled={!running}>
            Stop
          </button>
        </div>
      </header>

      <main className="app-main">
        <section className="top-controls">
          <div className="controls-lock">
            <span className="lock-pill">Running</span>
            <span>Top configuration is locked while the engine is active.</span>
          </div>

          <article className="card channel-card channel-a control-card">{channelAControl}</article>

          <article className="card route-card control-card">
            <div className="card-header route-header">
              <div>
                <p className="eyebrow">Unified Route</p>
                <h2>Route &amp; Diagnostics</h2>
                <p className="card-copy">Symmetric live view for both translation lanes with shared AST core.</p>
              </div>
            </div>

            <div className="route-network">
              <svg className="route-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                <line x1="18" y1="27" x2="42" y2="27" className="route-line route-line-blue" />
                <line x1="58" y1="27" x2="82" y2="27" className="route-line route-line-blue" />
                <line x1="18" y1="73" x2="42" y2="73" className="route-line route-line-green" />
                <line x1="58" y1="73" x2="82" y2="73" className="route-line route-line-green" />
              </svg>

              {routeNodeAInput}
              {routeNodeAOutput}

              <div className="ast-core">
                <div className="ast-ring" />
                <div className="ast-pill">AST</div>
                <p>Volc Engine S2S Stream</p>
              </div>

              {routeNodeBOutput}
              {routeNodeBInput}
            </div>
          </article>

          <article className="card channel-card channel-b control-card">{channelBControl}</article>
        </section>

        <section className="transcript-dock">
          <div className="dock-header">
            <div>
              <p className="eyebrow">Live Translation</p>
              <h2>Dual-Pane Transcript Dock</h2>
              <p className="card-copy">
                Smooth auto-scroll, source text dimmed, translated text emphasized for continuous reading.
              </p>
            </div>
          </div>

          <div className="transcript-grid">
            {transcriptPaneA}
            {transcriptPaneB}
          </div>
        </section>
      </main>

      {credentialsDrawer}
    </div>
  );
}
