/**
 * Colab Keep-Alive Script
 *
 * Paste this into your browser's JavaScript console while the Colab notebook
 * is open. It prevents Colab from disconnecting due to inactivity by:
 *   1. Simulating mouse activity every 30 seconds so the browser doesn't
 *      put the tab to sleep
 *   2. Clicking the "Reconnect" button automatically if the session drops
 *
 * HOW TO USE:
 *   1. Open your Colab notebook and start running the CFD worker loop
 *   2. Press F12 (or Cmd+Option+J on Mac) to open browser DevTools
 *   3. Click the "Console" tab
 *   4. Paste this entire script and press Enter
 *   5. You should see "[keep-alive] Started." in the console
 *   6. You can now minimize DevTools — the script keeps running
 *
 * To stop it: refresh the page, or type clearInterval(keepAliveTimer) in console
 */

(function () {
  let ticks = 0;

  function tryReconnect() {
    // Try the modern Colab toolbar connect button
    const connectBtn = document.querySelector('colab-connect-button');
    if (connectBtn && connectBtn.shadowRoot) {
      const inner = connectBtn.shadowRoot.querySelector('paper-button') ||
                    connectBtn.shadowRoot.querySelector('button');
      if (inner) {
        const text = inner.innerText || inner.textContent || '';
        if (text.toLowerCase().includes('reconnect') ||
            text.toLowerCase().includes('connect')) {
          inner.click();
          console.log('[keep-alive] Clicked reconnect at', new Date().toLocaleTimeString());
        }
      }
    }
  }

  function simulateActivity() {
    // Dispatch a mouse move event — prevents browser tab sleep
    document.dispatchEvent(new MouseEvent('mousemove', { bubbles: true }));

    // Also dispatch a key event occasionally
    if (ticks % 4 === 0) {
      document.dispatchEvent(new KeyboardEvent('keydown', {
        key: 'Shift',
        bubbles: true
      }));
    }
  }

  function tick() {
    ticks++;
    simulateActivity();
    tryReconnect();

    if (ticks % 10 === 0) {
      console.log(
        `[keep-alive] Still running — tick ${ticks} at`,
        new Date().toLocaleTimeString()
      );
    }
  }

  // Run every 30 seconds
  const keepAliveTimer = setInterval(tick, 30_000);

  console.log('[keep-alive] Started. Runs every 30s. Session should stay alive.');
  console.log('[keep-alive] To stop: clearInterval(' + keepAliveTimer + ')');
})();
