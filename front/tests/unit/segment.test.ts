import { describe, expect, it } from 'vitest';
import { applyTranslation, scan, serializeGroup } from '../../src/content/segment';

function setup(html: string) {
  document.body.innerHTML = html;
  return scan(document.body);
}

describe('segmentation par blocs', () => {
  it('garde une phrase découpée en balises dans un seul segment', () => {
    const r = setup('<p>Votre <b>solde</b> est de <span class="amt">25 000 FCFA</span> aujourd’hui.</p>');
    expect(r.groups).toHaveLength(1);
    expect(serializeGroup(r.groups[0]).text).toBe('Votre {B0}solde{/B0} est de {B1}25 000 FCFA{/B1} aujourd’hui.');
  });

  it('sépare les blocs et descend dans les conteneurs', () => {
    const r = setup('<div><h2>Frais</h2><p>Les frais sont de 1 %.</p><ul><li>Un</li><li>Deux</li></ul></div>');
    expect(r.groups.map((g) => serializeGroup(g).text)).toEqual(['Frais', 'Les frais sont de 1 %.', 'Un', 'Deux']);
  });

  it('ignore script, style, code, champs et data-amira-ignore', () => {
    const r = setup('<p>Texte</p><script>var a="x"</script><style>p{}</style><pre>code</pre><textarea>saisie</textarea><div data-amira-ignore>non</div><select><option>Choix</option></select>');
    expect(r.groups.map((g) => serializeGroup(g).text)).toEqual(['Texte']);
  });

  it('élément atomique dans une phrase : repère {E}', () => {
    const r = setup('<p>Montant <input name="m" value="5000"> FCFA</p>');
    expect(serializeGroup(r.groups[0]).text).toBe('Montant {E0} FCFA');
    // la valeur du champ n'apparaît jamais
    expect(JSON.stringify(serializeGroup(r.groups[0]).text)).not.toContain('5000');
  });

  it('descend dans un élément en ligne unique (pas de repère inutile)', () => {
    const r = setup('<button><span>Confirmer</span></button>');
    expect(serializeGroup(r.groups[0]).text).toBe('Confirmer');
  });

  it('collecte placeholder, aria-label, title, mais jamais value d’un champ', () => {
    const r = setup('<input name="a" placeholder="Numéro du bénéficiaire" value="690000000"><button aria-label="Fermer" title="Fermer la fenêtre">×</button><input type="submit" value="Envoyer">');
    expect(r.attrs.map((a) => `${a.attr}=${a.value}`)).toEqual(['placeholder=Numéro du bénéficiaire', 'aria-label=Fermer', 'title=Fermer la fenêtre', 'value=Envoyer']);
  });

  it('parcourt le shadow DOM ouvert', () => {
    document.body.innerHTML = '<div id="h"></div>';
    const root = document.getElementById('h')!.attachShadow({ mode: 'open' });
    root.innerHTML = '<p>Dans l’ombre</p>';
    const r = scan(document.body);
    expect(r.groups.map((g) => serializeGroup(g).text)).toEqual(['Dans l’ombre']);
    expect(r.shadowRoots).toHaveLength(1);
  });

  it('applique sur place puis restaure à l’identique', () => {
    const r = setup('<p id="p">Votre <b>solde</b> est faible.</p>');
    const before = document.getElementById('p')!.innerHTML;
    const g = r.groups[0];
    const ser = serializeGroup(g);
    const bold = document.querySelector('b')!;
    const a = applyTranslation(g, ser, 'TR {B0}SOLDE{/B0} TR');
    expect(document.getElementById('p')!.textContent).toBe('TR SOLDE TR');
    expect(document.querySelector('b')).toBe(bold); // même élément, pas recréé
    a.restore();
    expect(document.getElementById('p')!.innerHTML).toBe(before);
  });

  it('réordonne les balises en déplaçant les éléments d’origine', () => {
    const r = setup('<p id="p">Envoyer <b>A</b> à <i>B</i></p>');
    const before = document.getElementById('p')!.innerHTML;
    const g = r.groups[0];
    const ser = serializeGroup(g);
    const b = document.querySelector('b')!;
    const a = applyTranslation(g, ser, '{B1}b{/B1} ← {B0}a{/B0}');
    expect(document.getElementById('p')!.innerHTML).toBe('<i>b</i> ← <b>a</b>');
    expect(document.querySelector('b')).toBe(b);
    a.restore();
    expect(document.getElementById('p')!.innerHTML).toBe(before);
  });
});
