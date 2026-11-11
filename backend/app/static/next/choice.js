/* Sends this browser to the interface chosen on /admin (stored as smako.ui).
   /personal?ui=standard always shows the ordinary interface, and a link to a
   saved plan or a return from sign-in is never redirected. */
(() => {
  "use strict";
  try {
    const choice = localStorage.getItem("smako.ui"), url = new URL(location.href);
    if (!["a", "b"].includes(choice) || url.searchParams.has("ui") || url.search || url.hash) return;
    location.replace(`/ui/${choice}`);
  } catch (_) { /* no storage: the ordinary interface */ }
})();
