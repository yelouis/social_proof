/**
 * Shared rendering engine for Social Proof (Depth 1 Overlay & Depth 2 Sidepanel).
 * Implements design_ui_direction.md §1–§6.
 *
 * Invariant I3: Citation-first (quote + date + resolvable source link).
 * Invariant I5: Null axis rendered as plain reason, NEVER as 0 or empty bar.
 * Prohibition: Zero composite or average score.
 */

export const SocialProofRenderer = {
  /**
   * Formats an axis score or its null reason.
   * Enforces design_ui_direction.md §4: categorically different shape for null.
   *
   * @param {string} axisName
   * @param {{ score: number | null, reason: string | null }} axisData
   * @returns {string} HTML snippet
   */
  renderAxis(axisName, axisData) {
    if (!axisData || axisData.score === null) {
      const reason = (axisData && axisData.reason) ? axisData.reason.replace(/_/g, ' ') : 'insufficient data';
      return `
        <div class="sp-axis-row sp-axis-null" data-axis="${axisName}">
          <span class="sp-axis-label">${axisName}</span>
          <span class="sp-axis-null-indicator">─── ${reason} ───</span>
        </div>
      `;
    }

    const val = Number(axisData.score).toFixed(2);
    return `
      <div class="sp-axis-row sp-axis-scored" data-axis="${axisName}">
        <span class="sp-axis-label">${axisName}</span>
        <span class="sp-axis-score-val">${val}</span>
      </div>
    `;
  },

  /**
   * Renders Depth 1 overlay content.
   * @param {Object} data
   * @returns {string} HTML string
   */
  renderOverlay(data) {
    const { state, proposition, subject, topic, contrastQuote, assessment, tensionCount } = data;

    // State 1: Nothing in corpus
    if (state === 'nothing' || !subject) {
      return `
        <div class="sp-overlay-box sp-state-nothing">
          <div class="sp-header">
            <span class="sp-title-tag">CORPUS RECORD</span>
          </div>
          <div class="sp-body-notice">
            No first-hand record for this subject on this claim or topic in the current corpus.
          </div>
        </div>
      `;
    }

    // State 2: Topic only fallback
    if (state === 'topic_only') {
      return `
        <div class="sp-overlay-box sp-state-topic">
          <div class="sp-header">
            <span class="sp-title-tag">TOPIC SLICE</span>
            <div class="sp-subject-name">${subject.display_name}</div>
          </div>
          <div class="sp-body-notice">
            No specific proposition cleared the threshold. Showing topic slice: <strong>${topic || 'General'}</strong>.
          </div>
          <button class="sp-btn-expand" id="sp-btn-expand">View topic evidence →</button>
        </div>
      `;
    }

    // State 3: Proposition matched (design_ui_direction.md §6 Depth 1)
    const axesHtml = assessment && assessment.axes ? `
      <div class="sp-axes-grid">
        ${this.renderAxis('Consistency', assessment.axes.consistency)}
        ${this.renderAxis('Specificity', assessment.axes.specificity)}
        ${this.renderAxis('Updates', assessment.axes.update_integrity)}
        ${this.renderAxis('Even-handed', assessment.axes.even_handedness)}
      </div>
    ` : '';

    const quoteHtml = contrastQuote ? `
      <div class="sp-quote-card">
        <div class="sp-quote-meta">
          <span class="sp-quote-date">${contrastQuote.recorded_at ? contrastQuote.recorded_at.substring(0, 7) : 'Undated'}</span>
          <span class="sp-meta-dot">·</span>
          <span class="sp-quote-source">${contrastQuote.source_title || 'Direct Record'}</span>
          <span class="sp-meta-dot">·</span>
          <span class="sp-quote-venue">${contrastQuote.venue_type || 'first-hand'}</span>
        </div>
        <blockquote class="sp-quote-text">
          "${contrastQuote.quote_text}"
        </blockquote>
        <div class="sp-quote-footer">
          ${contrastQuote.source_url ? `<a href="${contrastQuote.source_url}" target="_blank" rel="noreferrer" class="sp-cite-link">▸ cite</a>` : '<span class="sp-cite-disabled">cite unavailable</span>'}
        </div>
      </div>
    ` : '';

    const tensionBanner = tensionCount && tensionCount > 0 ? `
      <div class="sp-tension-alert">
        <span class="sp-alert-icon">⚠</span>
        <span class="sp-alert-text">${tensionCount} detected tension${tensionCount > 1 ? 's' : ''} in corpus</span>
      </div>
    ` : '';

    const versionProvenance = assessment && assessment.rubric_version ? `
      <div class="sp-version-footer">rubric ${assessment.rubric_version}</div>
    ` : '';

    return `
      <div class="sp-overlay-box sp-state-matched">
        <div class="sp-header">
          <span class="sp-title-tag">ON THIS CLAIM</span>
          <button class="sp-btn-close" id="sp-btn-close" title="Dismiss">✕</button>
        </div>
        <div class="sp-prop-title">${proposition.canonical_text}</div>
        <div class="sp-subject-sub">${subject.display_name}</div>

        ${quoteHtml}
        ${tensionBanner}
        ${axesHtml}

        <div class="sp-footer-row">
          <button class="sp-btn-expand" id="sp-btn-expand">Full timeline and evidence →</button>
          ${versionProvenance}
        </div>
      </div>
    `;
  },

  /**
   * Renders Depth 2 Tension Card (design_ui_direction.md §5).
   * @param {Object} tension
   * @returns {string} HTML string
   */
  renderTensionCard(tension) {
    const typeLabel = (tension.type || 'TENSION').replace(/_/g, ' ').toUpperCase();
    const distinctionHtml = tension.stated_distinction ? `
      <div class="sp-distinction-block">
        <span class="sp-distinction-label">Stated Distinction:</span>
        <span class="sp-distinction-text">"${tension.stated_distinction}"</span>
      </div>
    ` : '';

    return `
      <div class="sp-tension-card" data-tension-id="${tension.tension_id}">
        <div class="sp-tension-header">
          <span class="sp-tension-badge">┌─ ${typeLabel}</span>
          <span class="sp-tension-severity">severity ${(tension.severity || 0.5).toFixed(2)} ─┐</span>
        </div>

        <div class="sp-claim-pair">
          <div class="sp-claim-side sp-claim-a">
            <div class="sp-claim-meta">${tension.claim_a.recorded_at ? tension.claim_a.recorded_at.substring(0, 10) : ''} · ${tension.claim_a.stance}</div>
            <blockquote class="sp-claim-quote">"${tension.claim_a.quote_text}"</blockquote>
          </div>

          <div class="sp-tension-gap">
            ─────────────── chronological interval ───────────────
          </div>

          <div class="sp-claim-side sp-claim-b">
            <div class="sp-claim-meta">${tension.claim_b.recorded_at ? tension.claim_b.recorded_at.substring(0, 10) : ''} · ${tension.claim_b.stance}</div>
            <blockquote class="sp-claim-quote">"${tension.claim_b.quote_text}"</blockquote>
          </div>
        </div>

        ${distinctionHtml}

        <div class="sp-tension-notice">
          No acknowledgement of the change was found in the corpus between these dates.
        </div>
      </div>
    `;
  }
};
