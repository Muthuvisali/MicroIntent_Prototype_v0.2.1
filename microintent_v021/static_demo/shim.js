// Static demo: runs the Python pipeline in the browser with Pyodide and answers the
// UI's /chat, /compare and /health calls locally, so the page needs no server.
// PYODIDE_INDEX and PY_FILES are injected by scripts/build_static.py.
(function () {
  const realFetch = window.fetch.bind(window);
  const ROUTES = new Set(["/chat", "/compare", "/health"]);

  const status = document.createElement("div");
  status.textContent = "Loading the Python runtime in your browser (one-time, about 10 seconds)…";
  status.style.cssText = "position:fixed;left:50%;bottom:18px;transform:translateX(-50%);background:#202124;color:#fff;" +
    "padding:10px 16px;border-radius:999px;font:13px Inter,Arial,sans-serif;z-index:9999;box-shadow:0 6px 20px rgba(0,0,0,.2)";
  document.addEventListener("DOMContentLoaded", () => document.body.appendChild(status));

  const ready = (async () => {
    const py = await loadPyodide({ indexURL: PYODIDE_INDEX });
    await py.loadPackage("pydantic");
    for (const file of PY_FILES) {
      const text = await (await realFetch(file)).text();
      const target = "/home/pyodide/" + file;
      py.FS.mkdirTree(target.slice(0, target.lastIndexOf("/")));
      py.FS.writeFile(target, text);
    }
    py.runPython("import sys; sys.path.insert(0, '/home/pyodide')");
    const api = py.pyimport("demo_api");
    status.remove();
    return api;
  })().catch((err) => {
    status.textContent = "Could not load the Python runtime: " + err.message;
    status.style.background = "#b3261e";
    throw err;
  });

  window.fetch = async (input, init = {}) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (url.origin !== location.origin || !ROUTES.has(url.pathname)) return realFetch(input, init);
    const api = await ready;
    const env = JSON.parse(api.handle(url.pathname, init.body || ""));
    return new Response(env.body, { status: env.status, headers: { "Content-Type": "application/json" } });
  };
})();
