// Capture the real app in a fresh browser context, without loading user sessions.
import {chromium} from "@playwright/test";
import {spawn} from "node:child_process";
import {mkdir} from "node:fs/promises";
import {fileURLToPath} from "node:url";
const base = process.env.ATLAS_DEMO_URL || "http://127.0.0.1:4173/atlas-recsys/";
const output = fileURLToPath(new URL("../../docs/images/", import.meta.url));
const server = process.env.ATLAS_DEMO_URL ? null : spawn(process.execPath, [fileURLToPath(new URL("./serve.js", import.meta.url))], {stdio:"ignore"});
let browser;
try {
  for (let i=0;i<50;i++) {try {if ((await fetch(base)).ok) break;} catch {} await new Promise(resolve => setTimeout(resolve,100));}
  browser = await chromium.launch({channel:process.env.ATLAS_BROWSER_CHANNEL || undefined});
  const page = await browser.newPage({viewport:{width:1440,height:1100},deviceScaleFactor:1});
  await page.goto(base);
  await page.locator("#model-status").filter({hasText:"Model ready"}).waitFor();
  await mkdir(output,{recursive:true});
  await page.screenshot({path:output+"atlas-demo.png"});
  await page.getByRole("button",{name:"Evidence",exact:true}).click();
  await page.screenshot({path:output+"atlas-evidence.png"});
  await page.getByRole("button",{name:"Explore",exact:true}).click();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:output+"atlas-mobile.png",fullPage:true});
  console.log("Captured desktop, evidence, and mobile screenshots of the actual application.");
} finally {if(browser) await browser.close();if(server) server.kill();}
