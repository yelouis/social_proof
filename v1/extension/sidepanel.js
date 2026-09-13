/**
 * Social Proof Browser Extension - Sidepanel Script (Depth 2 Expanded View).
 * Implements design_ui_direction.md §2–§5.
 */

import { SocialProofRenderer } from './render.js';

const API_BASE = 'http://127.0.0.1:8787';

async function initSidepanel() {
  const { activePayload, apiToken } = await chrome.storage.local.get(['activePayload', 'apiToken']);
  if (!activePayload || !activePayload.subject) {
    document.getElementById('panel-subject-name').textContent = 'No active subject';
    return;
  }

  const { subject, topic, assessment } = activePayload;
  document.getElementById('panel-subject-name').textContent = subject.display_name;
  document.getElementById('panel-topic-info').textContent = `Topic: ${topic || 'Global'} · rubric ${assessment?.rubric_version || 'v1.0'}`;

  // 1. Render Rubric Axes
  const axesContainer = document.getElementById('panel-axes-container');
  if (assessment && assessment.axes) {
    axesContainer.innerHTML = `
      ${SocialProofRenderer.renderAxis('Consistency', assessment.axes.consistency)}
      ${SocialProofRenderer.renderAxis('Specificity', assessment.axes.specificity)}
      ${SocialProofRenderer.renderAxis('Update Integrity', assessment.axes.update_integrity)}
      ${SocialProofRenderer.renderAxis('Even-handedness', assessment.axes.even_handedness)}
    `;
  }

  // 2. Fetch & Render Tensions
  const tensionsContainer = document.getElementById('panel-tensions-container');
  try {
    const tensionIds = (assessment && assessment.axis_evidence)
      ? Object.values(assessment.axis_evidence).flat()
      : [];

    if (tensionIds.length === 0) {
      tensionsContainer.innerHTML = '<div class="sp-panel-sub">No published tensions detected for this slice.</div>';
    } else {
      tensionsContainer.innerHTML = '';
      for (const tid of tensionIds) {
        const res = await fetch(`${API_BASE}/tensions/${tid}`, {
          headers: { 'Authorization': `Bearer ${apiToken}` }
        });
        if (res.ok) {
          const tData = await res.json();
          tensionsContainer.innerHTML += SocialProofRenderer.renderTensionCard(tData);
        }
      }
    }
  } catch (err) {
    console.error('Error fetching tensions:', err);
  }

  // 3. Fetch & Render Timeline
  const timelineContainer = document.getElementById('panel-timeline-container');
  try {
    const res = await fetch(`${API_BASE}/subjects/${subject.subject_id}/timeline?topic=${encodeURIComponent(topic || 'global')}`, {
      headers: { 'Authorization': `Bearer ${apiToken}` }
    });
    if (res.ok) {
      const tData = await res.json();
      if (!tData.claims || tData.claims.length === 0) {
        timelineContainer.innerHTML = '<div class="sp-panel-sub">No claims recorded.</div>';
      } else {
        timelineContainer.innerHTML = tData.claims.map(c => `
          <div class="sp-claim-card">
            <div class="sp-claim-meta">${c.recorded_at ? c.recorded_at.substring(0, 10) : 'Undated'} · ${c.source_title} · ${c.venue_type} · stance: ${c.stance}</div>
            <blockquote class="sp-claim-quote">"${c.quote_text}"</blockquote>
            ${c.source_url ? `<a href="${c.source_url}" target="_blank" rel="noreferrer" class="sp-cite-link">▸ cite</a>` : ''}
          </div>
        `).join('');
      }
    }
  } catch (err) {
    console.error('Error fetching timeline:', err);
  }
}

document.addEventListener('DOMContentLoaded', initSidepanel);
