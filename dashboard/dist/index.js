/* jev-live-flow dashboard tab — plain IIFE, no build step.
 * Renders the flow UI in a same-origin iframe so it works from any client
 * that can reach the dashboard (no hardcoded host/port).
 */
(function () {
  "use strict";

  var SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;
  var React = SDK.React;

  function FlowPage() {
    return React.createElement("iframe", {
      src: "/api/plugins/jev-live-flow/app",
      title: "Jev Live Flow",
      style: {
        width: "100%",
        height: "calc(100vh - 130px)",
        border: "0",
        borderRadius: "10px",
        background: "transparent",
        display: "block"
      }
    });
  }

  window.__HERMES_PLUGINS__.register("jev-live-flow", FlowPage);
})();
