from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import webbrowser


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Repeated Word Counter</title>
  <style>
    :root { color-scheme: light; --ink: #202642; --muted: #68708a; --line: #e3e7f2; }
    body { font: 16px system-ui, sans-serif; margin: 3rem auto; max-width: 760px; padding: 0 1rem; color: var(--ink); background: #f7f8fc; }
    h1 { margin-bottom: .5rem; color: #5b35b5; }
    .controls { display: flex; flex-wrap: wrap; align-items: center; gap: 1rem; margin: 1.5rem 0; }
    button { padding: .6rem 1rem; color: white; background: #6842c2; border: 0; border-radius: .5rem; font: inherit; font-weight: 650; cursor: pointer; }
    button:hover:not(:disabled) { background: #50309b; }
    button:disabled { background: #aaa3ba; cursor: not-allowed; }
    input[type="file"] { max-width: 100%; }
    #status { min-height: 1.5em; color: var(--muted); }
    table { overflow: hidden; border-collapse: separate; border-spacing: 0; margin-top: 1rem; width: 100%; background: white; border: 1px solid var(--line); border-radius: .75rem; box-shadow: 0 6px 20px #27204a12; }
    th, td { border-bottom: 1px solid var(--line); padding: .75rem; text-align: left; }
    th { color: white; background: #374477; font-size: .9rem; letter-spacing: .03em; }
    tbody tr:nth-child(even) { background: #f3f0ff; }
    tbody tr:hover { background: #e8e1ff; }
    th:last-child, td:last-child { text-align: right; }
    .word { color: #5b35b5; font-weight: 700; }
    .count { display: inline-block; min-width: 1.5rem; padding: .15rem .55rem; color: #075d4c; background: #c9f4e5; border-radius: 999px; font-weight: 750; text-align: center; }
    .count.high { color: #9b2c20; background: #ffe0d9; }
    [hidden] { display: none; }
  </style>
</head>
<body>
  <h1>Repeated Word Counter</h1>
  <p>Choose a text file to see words that occur more than once. Matching ignores
  capitalization and punctuation.</p>
  <div class="controls">
    <label for="file-input">Select a text file:</label>
    <input id="file-input" type="file" accept=".txt,text/plain">
    <button id="export-button" type="button" disabled>Export CSV</button>
  </div>
  <p id="status" role="status" aria-live="polite">No file selected.</p>
  <table id="results" hidden>
    <thead><tr><th>Word</th><th>Count</th></tr></thead>
    <tbody></tbody>
  </table>
  <script>
    const fileInput = document.querySelector("#file-input");
    const exportButton = document.querySelector("#export-button");
    const status = document.querySelector("#status");
    const table = document.querySelector("#results");
    const tbody = table.querySelector("tbody");
    let repeatedWords = [];
    let selectedFileName = "word-counts";

    fileInput.addEventListener("change", async () => {
      const file = fileInput.files[0];
      repeatedWords = [];
      tbody.replaceChildren();
      table.hidden = true;
      exportButton.disabled = true;
      if (!file) {
        status.textContent = "No file selected.";
        return;
      }
      

      try {
        const text = await file.text();
        const words = text.toLocaleLowerCase().match(/[\\p{L}\\p{N}_]+/gu) || [];
        const counts = new Map();
        for (const word of words) counts.set(word, (counts.get(word) || 0) + 1);
        repeatedWords = [...counts.entries()]
          .filter(([, count]) => count > 1)
          .sort(([wordA], [wordB]) => wordA.localeCompare(wordB));
        selectedFileName = file.name.replace(/\\.[^.]*$/, "") || "word-counts";

        if (repeatedWords.length === 0) {
          status.textContent = `No repeated words found in ${file.name}.`;
          return;
        }

        for (const [word, count] of repeatedWords) {
          const row = document.createElement("tr");
          const wordCell = document.createElement("td");
          const countCell = document.createElement("td");
          const countBadge = document.createElement("span");
          wordCell.className = "word";
          wordCell.textContent = word;
          countBadge.className = count >= 5 ? "count high" : "count";
          countBadge.textContent = count;
          countCell.append(countBadge);
          row.append(wordCell, countCell);
          tbody.append(row);
        }
        table.hidden = false;
        exportButton.disabled = false;
        status.textContent = `Found ${repeatedWords.length} repeated word(s) in ${file.name}.`;
      } catch (error) {
        status.textContent = `Could not read the selected file: ${error.message}`;
      }
    });

    exportButton.addEventListener("click", () => {
      const csvCell = value => `"${String(value).replaceAll('"', '""')}"`;
      const csv = ["Word,Count", ...repeatedWords.map(([word, count]) =>
        `${csvCell(word)},${count}`)].join("\\r\\n");
      const url = URL.createObjectURL(new Blob(["\\uFEFF", csv], {
        type: "text/csv;charset=utf-8"
      }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `${selectedFileName}-repeated-words.csv`;
      link.click();
      URL.revokeObjectURL(url);
    });
  </script>
</body>
</html>
"""


class PageHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/":
            self.send_error(404)
            return

        content = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main() -> None:
    with ThreadingHTTPServer(("127.0.0.1", 0), PageHandler) as server:
        address = f"http://127.0.0.1:{server.server_port}/"
        print(f"Opening repeated word counter at {address}")
        webbrowser.open(address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nRepeated word counter stopped.")

if __name__ == "__main__":
    main()
