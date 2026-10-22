import { build } from 'esbuild';
import { cp, mkdir, readFile, writeFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(process.argv[2] || path.join(root, 'dist'));
if (output === root || output === path.resolve(root, '../..')) throw new Error('Build output must be a separate directory');
await mkdir(path.join(output, 'assets'), { recursive: true });
await build({ entryPoints: [path.join(root, 'app.mjs')], outfile: path.join(output, 'assets/library.js'), bundle: true, format: 'esm', platform: 'browser', target: 'es2022', minify: true, legalComments: 'eof' });
for (const name of ['index.html', 'styles.css']) await cp(path.join(root, name), path.join(output, name));
const dependencies = [
  ['pdfjs-dist/build/pdf.worker.min.mjs', 'pdf.worker.mjs'],
  ['pdfjs-dist/cmaps', 'cmaps'], ['pdfjs-dist/standard_fonts', 'standard_fonts'], ['pdfjs-dist/wasm', 'pdf-wasm'],
  ['tesseract.js/dist/worker.min.js', 'ocr-worker.js'],
  ['tesseract.js/dist/worker.min.js.LICENSE.txt', 'worker.min.js.LICENSE.txt'],
  ['@tesseract.js-data/por/4.0.0_best_int/por.traineddata.gz', 'por.traineddata.gz'],
  ['@tesseract.js-data/eng/4.0.0_best_int/eng.traineddata.gz', 'eng.traineddata.gz'],
];
for (const [source, target] of dependencies) await cp(path.join(root, 'node_modules', source), path.join(output, 'assets', target), { recursive: true });
for (const name of await readdir(path.join(root, 'node_modules/tesseract.js-core'))) {
  if (/^tesseract-core-(?:simd-|relaxedsimd-)?lstm\.(?:wasm|wasm\.js)$/.test(name)) await cp(path.join(root, 'node_modules/tesseract.js-core', name), path.join(output, 'assets', name));
}
const licenses = [];
for (const packageName of ['pdfjs-dist', 'tesseract.js', 'tesseract.js-core', 'fflate', '@tesseract.js-data/por', '@tesseract.js-data/eng']) {
  const packageRoot = path.join(root, 'node_modules', packageName);
  const pkg = JSON.parse(await readFile(path.join(packageRoot, 'package.json'), 'utf8'));
  let license = '';
  for (const name of ['LICENSE', 'LICENSE.txt', 'LICENSE.md']) { try { license = await readFile(path.join(packageRoot, name), 'utf8'); break; } catch {} }
  licenses.push(`${packageName}@${pkg.version}\nLicense: ${pkg.license}\n${license}`);
}
await writeFile(path.join(output, 'THIRD_PARTY_LICENSES.txt'), licenses.join('\n\n---\n\n'));
await writeFile(path.join(output, 'library-config.json'), JSON.stringify({ starter: null }));
console.log(JSON.stringify({ output, app: 'Daemon personal library', dependencies: 'pinned, self-hosted' }));
