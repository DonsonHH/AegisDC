const sharp = require(process.argv[2]);
const path = require('node:path');
async function main() {
  const outputs = {};
  for (const name of ['observation-timing', 'source-authority']) {
    outputs[name] = await sharp(path.join(process.argv[3], name + '.svg'), { density: 96 }).png().toFile(path.join(process.argv[4], name + '.png'));
  }
  process.stdout.write(JSON.stringify({ versions: sharp.versions, outputs }) + '\n');
}
main().catch(error => { process.stderr.write(String(error) + '\n'); process.exitCode = 1; });
