/**
 * Social Proof Browser Extension - Content Script.
 * Selection-triggered investigation and Shadow DOM overlay.
 *
 * Implements design_local_api_and_clients.md §4, §5 and design_ui_direction.md §6.
 * Invariant I2: Selection and bounded context are sent to /resolve for matching only.
 * Invariant I8: Shadow DOM ensures host page DOM is 100% unmodified after dismiss.
 */

import { SocialProofRenderer } from './render.js';

let currentOverlayHost = null;

function removeOverlay() {
  if (currentOverlayHost) {
    currentOverlayHost.remove();
    currentOverlayHost = null;
  }
}

function getSelectionContext(selection) {
  if (!selection || selection.rangeCount === 0) return { before: '', after: '' };
  const range = selection.getRangeAt(0);
  const container = range.commonAncestorContainer;
  const fullText = container.textContent || '';
  const selectedText = selection.toString();
  const idx = fullText.indexOf(selectedText);

  let before = '';
  let after = '';
  if (idx !== -1) {
    before = fullText.substring(Math.max(0, idx - 500), idx).trim();
    after = fullText.substring(idx + selectedText.length, idx + selectedText.length + 500).trim();
  }
  return { before, after };
}

async function handleSelection() {
  const selection = window.getSelection();
  const selectedText = selection ? selection.toString().trim() : '';

  // Minimal length threshold to prevent firing on accidental clicks
  if (!selectedText || selectedText.length < 10) {
    return;
  }

  // Position near selection
  const range = selection.getRangeAt(0);
  const rect = range.getBoundingClientRect();
  const { before, after } = getSelectionContext(selection);

  // Send message to background service worker to query local API with Bearer token
  chrome.runtime.sendMessage({
    type: 'RESOLVE_SELECTION',
    payload: {
      selected_text: selectedText,
      context_before: before,
      context_after: after,
      page_url: window.location.href,
      page_title: document.title
    }
  }, (response) => {
    if (chrome.runtime.lastError || !response || !response.ok) {
      console.debug('Social Proof API resolution skipped or unauthenticated.');
      return;
    }

    mountOverlay(response.data, rect);
  });
}

function mountOverlay(data, targetRect) {
  removeOverlay();

  // Create isolated custom element and closed Shadow DOM to protect page DOM integrity
  const host = document.createElement('social-proof-overlay-host');
  host.style.position = 'absolute';
  host.style.left = `${window.scrollX + targetRect.left}px`;
  host.style.top = `${window.scrollY + targetRect.bottom + 8}px`;
  host.style.zIndex = '2147483647';

  const shadow = host.attachShadow({ mode: 'open' });

  // Load styles
  const styleLink = document.createElement('link');
  styleLink.rel = 'stylesheet';
  styleLink.href = chrome.runtime.getURL('overlay.css');
  shadow.appendChild(styleLink);

  const container = document.createElement('div');
  container.innerHTML = SocialProofRenderer.renderOverlay(data);
  shadow.appendChild(container);

  // Bind close action
  const closeBtn = container.querySelector('#sp-btn-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      removeOverlay();
    });
  }

  // Bind expand action to open Depth 2 Sidepanel
  const expandBtn = container.querySelector('#sp-btn-expand');
  if (expandBtn) {
    expandBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      chrome.runtime.sendMessage({
        type: 'OPEN_EXPANDED_VIEW',
        payload: data
      });
      removeOverlay();
    });
  }

  document.body.appendChild(host);
  currentOverlayHost = host;
}

// Listen for selection completion
document.addEventListener('mouseup', () => {
  setTimeout(handleSelection, 50);
});

// Dismiss on outside click or Escape
document.addEventListener('mousedown', (e) => {
  if (currentOverlayHost && !currentOverlayHost.contains(e.target)) {
    removeOverlay();
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    removeOverlay();
  }
});
