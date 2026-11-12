/* Sends this browser to the interface chosen on /admin (stored as smako.ui).
   /personal?ui=standard always shows the ordinary interface, and a link to a
   saved plan is never redirected. */
(() => {
  "use strict";
  try {
    const choice = localStorage.getItem("smako.ui"), url = new URL(location.href);
    if (!["a", "b"].includes(choice) || url.searchParams.has("ui") || url.search) return;
    // Sign-in with an outside provider returns to /personal#account; the chosen interface has its own account screen.
    if (url.hash === "#account") location.replace(`/ui/${choice}#konto`);
    else if (!url.hash) location.replace(`/ui/${choice}`);
  } catch (_) { /* no storage: the ordinary interface */ }
})();
