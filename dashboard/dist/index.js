/* jev-live-flow dashboard tab — plain IIFE, no build step.
 *
 * hermes-webui does not mount dashboard/plugin_api.py (WebUI MVP ignores it),
 * so the tab embeds the plugin's own UI server on the same host, port 8780.
 * That works from any client that can reach the dashboard. Start the server
 * first (jev_live_flow_start) if the frame is blank.
 */
(function () {
  "use strict";

  var SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;
  var React = SDK.React;

  function flowUrl() {
    var host = window.location.hostname || "127.0.0.1";
    var proto = window.location.protocol === "https:" ? "https:" : "http:";
    return proto + "//" + host + ":8780/";
  }

  function FlowPage() {
    var url = flowUrl();
    return React.createElement(
      "div",
      { style: { display: "flex", flexDirection: "column", gap: "8px" } },
      React.createElement(
        "div",
        { style: { fontSize: "12px", opacity: 0.65 } },
        "Live flow · served from " + url + " · start it with jev_live_flow_start if blank"
      ),
      React.createElement("iframe", {
        src: url,
        title: "Jev Live Flow",
        style: {
          width: "100%",
          height: "calc(100vh - 160px)",
          border: "0",
          borderRadius: "10px",
          background: "#0b0f14",
          display: "block"
        }
      })
    );
  }

  window.__HERMES_PLUGINS__.register("jev-live-flow", FlowPage);
})();
