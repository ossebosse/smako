/* Sends this browser to its Smako interface. Owner decision 2026-11-20: Alternativ A
   (flikar) is the default; /admin can choose B or the classic page for this browser
   (stored as smako.ui). /personal?ui=standard always shows the classic page, and a
   link to a saved plan is never redirected. */
(() => {
  "use strict";
  let stored = null;
  try { stored = localStorage.getItem("smako.ui"); } catch (_) { /* no storage: the default */ }
  const choice = stored || "a", url = new URL(location.href);
  if (!["a", "b"].includes(choice) || url.searchParams.has("ui") || url.search) return;
  // Sign-in with an outside provider returns to /personal#account; the chosen interface has its own account screen.
  if (url.hash === "#account") location.replace(`/ui/${choice}#konto`);
  else if (!url.hash) location.replace(`/ui/${choice}`);
})();
