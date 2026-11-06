// The playground: the real Butterfly compiler, run in the browser by Pyodide
// (Python compiled to WebAssembly).
(function () {
  var editor = document.getElementById("editeur");
  if (!editor) return;

  var status = document.getElementById("statut");
  var runButton = document.getElementById("executer");
  var picker = document.getElementById("choix-exemple");
  var output = document.querySelector("#panneau-sortie code");
  var pythonOut = document.querySelector("#panneau-python code");
  var examples = JSON.parse(document.getElementById("exemples").textContent);

  // --- Picking an example, and sharing through the address (#code=...) ----------
  var empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "(my program)";
  picker.appendChild(empty);
  examples.forEach(function (example, i) {
    var option = document.createElement("option");
    option.value = String(i);
    option.textContent = example.titre + " : " + example.description;
    picker.appendChild(option);
  });

  function codeFromAddress() {
    var m = /^#code=(.*)$/.exec(window.location.hash);
    if (!m) return null;
    try { return decodeURIComponent(m[1]); } catch (e) { return null; }
  }
  var start = codeFromAddress();
  if (start !== null) {
    editor.value = start;
  } else {
    var initial = examples.length > 2 ? 2 : 0; // the diamond
    editor.value = examples[initial].source;
    picker.value = String(initial);
  }
  // A "Try this program" link opened in the already loaded page.
  window.addEventListener("hashchange", function () {
    var code = codeFromAddress();
    if (code !== null) {
      editor.value = code;
      picker.value = "";
    }
  });
  picker.addEventListener("change", function () {
    if (picker.value !== "") editor.value = examples[Number(picker.value)].source;
  });

  // --- Tabs ---------------------------------------------------------------------
  var outputTab = document.getElementById("onglet-sortie");
  var pythonTab = document.getElementById("onglet-python");
  var outputPanel = document.getElementById("panneau-sortie");
  var pythonPanel = document.getElementById("panneau-python");
  function showTab(outputVisible) {
    outputTab.setAttribute("aria-selected", String(outputVisible));
    pythonTab.setAttribute("aria-selected", String(!outputVisible));
    outputPanel.hidden = !outputVisible;
    pythonPanel.hidden = outputVisible;
  }
  outputTab.addEventListener("click", function () { showTab(true); });
  pythonTab.addEventListener("click", function () { showTab(false); });

  // --- Loading the compiler -----------------------------------------------------------
  var runPython = null;
  var SCRIPT = [
    "import json",
    "from butterfly.compiler import check, execute, transpile",
    "from butterfly.errors import context",
    "def run(source):",
    "    errors = check(source)",
    "    if errors:",
    "        return json.dumps({'ok': False, 'errors': [context(e, source) for e in errors]})",
    "    r = execute(source)",
    "    return json.dumps({",
    "        'ok': True, 'output': r.output, 'python': transpile(source),",
    "        'error': context(r.error, source) if r.error else None})",
  ].join("\n");

  function fail(message) {
    status.textContent = message;
    output.textContent = message;
  }

  if (typeof loadPyodide !== "function") {
    fail("Could not load Python (Pyodide): check your connection, then reload the page.");
    return;
  }

  loadPyodide()
    .then(function (pyodide) {
      return fetch("butterfly.zip")
        .then(function (response) { return response.arrayBuffer(); })
        .then(function (zip) {
          pyodide.unpackArchive(zip, "zip");
          pyodide.runPython(SCRIPT);
          runPython = pyodide.globals.get("run");
          runButton.disabled = false;
          status.textContent = "Ready.";
        });
    })
    .catch(function (error) { fail("Loading failed: " + error); });

  function runProgram() {
    if (!runPython) return;
    var result = JSON.parse(runPython(editor.value));
    if (!result.ok) {
      output.textContent = result.errors.join("\n");
      pythonOut.textContent = "";
      status.textContent = result.errors.length + " error(s) in the program.";
      showTab(true);
      return;
    }
    var text = result.output;
    if (result.error) {
      var before = text.replace(/\n$/, "");
      text = (before ? before + "\n" : "") + result.error;
    }
    output.textContent = text || "(the program printed nothing)";
    pythonOut.textContent = result.python;
    status.textContent = result.error ? "Runtime error." : "Done.";
    showTab(true);
  }
  runButton.addEventListener("click", runProgram);
  editor.addEventListener("keydown", function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      runProgram();
    }
  });
})();
