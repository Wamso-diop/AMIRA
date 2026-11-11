/** Styles injectés dans la page : marqueurs discrets, mode bilingue, bulle « original au survol ». */
export const PAGE_CSS = `
[data-amira-state="kept"]::before{
  content:"⚠";display:inline-block;margin-inline-end:.3em;font:700 .8em/1 system-ui,sans-serif;
  color:#C2134C;vertical-align:baseline;cursor:help;
}
[data-amira-bi]::after{
  content:attr(data-amira-bi);display:block;margin-top:.15em;padding-inline-start:.5em;
  border-inline-start:3px solid #EFD109;color:#481C4B;font-size:.92em;font-style:normal;font-weight:600;
  white-space:pre-wrap;
}
[data-amira-state="tr"][data-amira-hover]{text-decoration:underline dotted #E01D5B 1px;text-underline-offset:3px}
`;

export const TOOLTIP_CSS = `
:host{all:initial}
.tip{position:fixed;z-index:2147483647;max-width:min(360px,90vw);padding:8px 10px;border-radius:2px 12px 12px 12px;
  background:#481C4B;color:#fff;font:500 13px/1.35 system-ui,sans-serif;pointer-events:none;
  box-shadow:0 0 0 2px #EFD109;}
.tip[hidden]{display:none}
.tip b{display:block;font-weight:700;color:#EFD109;margin-bottom:2px;font-size:11px}
`;

export function injectPageStyle(root: Document | ShadowRoot): void {
  if (root.nodeType === 9) {
    root = root as Document;
    if (root.getElementById('amira-page-style')) return;
    const style = root.createElement('style');
    style.id = 'amira-page-style';
    style.setAttribute('data-amira-ignore', '');
    style.textContent = PAGE_CSS;
    (root.head ?? root.documentElement).appendChild(style);
    return;
  }
  try {
    const sheet = new CSSStyleSheet();
    sheet.replaceSync(PAGE_CSS);
    root = root as ShadowRoot;
    if (!root.adoptedStyleSheets.some((s) => (s as CSSStyleSheet & { __amira?: boolean }).__amira)) {
      (sheet as CSSStyleSheet & { __amira?: boolean }).__amira = true;
      root.adoptedStyleSheets = [...root.adoptedStyleSheets, sheet];
    }
  } catch {
    /* navigateur sans feuilles adoptées : pas de marqueur visuel dans ce shadow DOM */
  }
}
