// Local QA server; the deployed application is hosted by GitHub Pages.
import {createServer} from "node:http";
import {readFile} from "node:fs/promises";
import {fileURLToPath} from "node:url";
const root = fileURLToPath(new URL("../", import.meta.url));
const types = {"index.html":"text/html", "style.css":"text/css", "app.js":"text/javascript", "engine.js":"text/javascript", "model.json":"application/json", "evidence.json":"application/json", "favicon.svg":"image/svg+xml"};
createServer(async (request, response) => {
  const path = new URL(request.url, "http://127.0.0.1").pathname;
  const name = path === "/atlas-recsys/" ? "index.html" : path.replace(/^\/atlas-recsys\//, "");
  if (!Object.hasOwn(types, name)) {response.writeHead(404);response.end("Not found");return;}
  try {const data = await readFile(root + name);response.writeHead(200,{"Content-Type":types[name],"Cache-Control":"no-store"});response.end(data);}
  catch {response.writeHead(500);response.end("Unable to load site asset");}
}).listen(4173,"127.0.0.1");
