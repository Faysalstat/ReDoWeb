// Prefixes every selector in a plain CSS file with a scope class.
// Usage (from client-ng/): node scripts/scope-admin-css.js ../frontend/src/styles.css src/app/admin/admin-classic.css .classic-admin
// :root/html/body become the scope itself; @media/@supports bodies are recursed;
// @import and @font-face/@keyframes are passed through.
const fs = require('fs');
const [, , inFile, outFile, scope] = process.argv;
const src = fs.readFileSync(inFile, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');

function scopeSelector(sel) {
  return sel
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      if (/^(:root|html|body)$/.test(s)) return scope;
      if (/^(html|body)\b/.test(s)) return scope + s.replace(/^(html|body)/, '');
      return `${scope} ${s}`;
    })
    .join(',\n');
}

function transform(css) {
  let out = '';
  let i = 0;
  while (i < css.length) {
    const rest = css.slice(i).trimStart();
    if (rest.startsWith('@import')) {
      // the URL itself contains ';' (Google Fonts weights), so end at ')' then ';'
      const start = css.indexOf('@import', i);
      const end = css.indexOf(';', css.indexOf(')', start)) + 1;
      out += css.slice(start, end) + '\n';
      i = end;
      continue;
    }
    const open = css.indexOf('{', i);
    const semi = css.indexOf(';', i);
    if (open === -1) break;
    // statement at-rule like @import ...;
    if (semi !== -1 && semi < open && css.slice(i, semi).trim().startsWith('@')) {
      out += css.slice(i, semi + 1).trim() + '\n';
      i = semi + 1;
      continue;
    }
    const head = css.slice(i, open).trim();
    // find matching close brace
    let depth = 1;
    let j = open + 1;
    while (depth > 0 && j < css.length) {
      if (css[j] === '{') depth++;
      else if (css[j] === '}') depth--;
      j++;
    }
    const body = css.slice(open + 1, j - 1);
    if (head.startsWith('@media') || head.startsWith('@supports')) {
      out += `${head} {\n${transform(body)}}\n`;
    } else if (head.startsWith('@')) {
      out += `${head} {${body}}\n`;
    } else if (/^html$/.test(head) && /scroll-behavior/.test(body)) {
      // page-level smooth scrolling isn't the admin panel's to set
    } else {
      out += `${scopeSelector(head)} {${body}}\n`;
    }
    i = j;
  }
  return out;
}

const header =
  '/* GENERATED from frontend/src/styles.css by scoping every rule under .' +
  scope.slice(1) +
  ' so the copied admin panel keeps its classic look inside client-ng without\n' +
  '   leaking into (or being overridden by) the Tailwind pages. Regenerate rather than hand-edit. */\n';
fs.writeFileSync(outFile, header + transform(src));
