from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import webbrowser


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Repeated Word Counter</title>
  <style>
    body { font: 16px system-ui, sans-serif; margin: 3rem auto; max-width: 760px; padding: 0 1rem; color: #202124; }
    h1 { margin-bottom: .5rem; }
    .controls { display: flex; flex-wrap: wrap; align-items: center; gap: 1rem; margin: 1.5rem 0; }
    button { padding: .6rem 1rem; cursor: pointer; }
    button:disabled { cursor: not-allowed; }
    #status { min-height: 1.5em; }
    table { border-collapse: collapse; margin-top: 1rem; width: 100%; }
    th, td { border-bottom: 1px solid #dadce0; padding: .65rem; text-align: left; }
    th:last-child, td:last-child { text-align: right; }
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
          wordCell.textContent = word;
          countCell.textContent = count;
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
