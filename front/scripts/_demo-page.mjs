// Page bancaire de démonstration (libellés de l'environnement de test), partagée par les captures du livrable et le test de l'extension autonome.
export const html = `<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Banque démo</title><style>
*{box-sizing:border-box}body{margin:0;font:15px/1.45 'Helvetica Neue',Arial,sans-serif;color:#17324d;background:#eef3f8}
header{background:#0b3d6b;color:#fff;padding:16px 36px;display:flex;justify-content:space-between;align-items:center}
header b{font-size:20px;letter-spacing:.02em}header nav{display:flex;gap:26px;font-size:14px;opacity:.92}
main{max-width:1040px;margin:26px auto;padding:0 28px;display:grid;grid-template-columns:1.1fr .9fr;gap:22px}
h1{grid-column:1/-1;margin:4px 0 0;font-size:30px}
.card{background:#fff;border-radius:14px;padding:22px 24px;border:1px solid #d9e3ee}
.solde{background:#0b5cab;color:#fff;border-color:#0b5cab}.solde small{opacity:.85;font-size:13px;display:block}.solde strong{font-size:38px;display:block;margin:4px 0 14px}
.btns{display:flex;gap:12px}.btn{background:#ffd84d;color:#1a2b3c;border:0;border-radius:999px;padding:10px 20px;font-weight:700;font-size:14px}
.btn.alt{background:rgba(255,255,255,.18);color:#fff}
h2{margin:0 0 12px;font-size:17px}
.row{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid #e6edf4}.row:last-child{border:0}
.row span:first-child{color:#5a7391}.row b{font-variant-numeric:tabular-nums}
label{display:block;font-size:13px;color:#5a7391;margin:12px 0 4px}.in{border:1px solid #b9c9da;border-radius:8px;padding:10px 12px;background:#f8fbfe;color:#17324d;min-height:40px}
.alert{grid-column:1/-1;background:#fff4e5;border:1px solid #f2c27b;border-left:6px solid #e8890c;border-radius:10px;padding:14px 18px;font-weight:600}
.err{grid-column:1/-1;background:#fdecee;border:1px solid #f1a9b1;border-left:6px solid #d62839;border-radius:10px;padding:14px 18px;font-weight:600;display:none}
.tot b{font-size:20px}.tx .row span:first-child{color:#17324d}
</style></head><body>
<header><b>Banque démo</b><nav><span>Sécurité</span><span>Récapitulatif</span><span>Confirmation</span></nav></header>
<main>
<h1>Votre compte</h1>
<section class="card solde"><small>Solde disponible</small><strong>250 000 FCFA</strong><div class="btns"><button class="btn">Effectuer un transfert</button><button class="btn alt">Consulter les frais</button></div></section>
<section class="card"><h2>Compte courant</h2><div class="row"><span>Numéro de compte</span><b>CM21 1000 2000 3000 4000</b></div><div class="row"><span>Frais de transfert</span><b>500 FCFA</b></div><div class="row tot"><span>Total à débiter</span><b>25 500 FCFA</b></div></section>
<section class="card"><h2>Effectuer un transfert</h2><label>Nom du bénéficiaire</label><div class="in">Ada Ngono</div><label>Numéro de téléphone</label><div class="in">+237 699 12 34 56</div><label>Montant à envoyer</label><div class="in">25 000 FCFA</div><label>Motif du transfert</label><div class="in"></div></section>
<section class="card tx"><h2>Transactions récentes</h2><div class="row"><span>Salaire reçu</span><b>+ 180 000 FCFA</b></div><div class="row"><span>Transfert reçu</span><b>+ 15 000 FCFA</b></div><div class="row"><span>Facture électricité</span><b>− 22 400 FCFA</b></div></section>
<div class="alert" role="alert">Alerte de sécurité : vérifiez le numéro du bénéficiaire avant de continuer.</div>
<div class="err" id="err" role="alert">Solde insuffisant pour effectuer ce transfert.</div>
</main></body></html>`;
