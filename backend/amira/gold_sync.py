"""Rechargement du CSV gold sans redémarrer : dès que le fichier change, l'import est rejoué avant la traduction."""
import logging
import os
import threading

log = logging.getLogger("amira")


class GoldSync:
    """path : le CSV ; validator : le natif qui le relit (vide = pas de rechargement, import à la main seulement)."""

    def __init__(self, path: str, validator: str, lang: str = "ff"):
        self.path, self.validator, self.lang = path, validator.strip(), lang
        self.mtime = None
        self._lock = threading.Lock()

    def __call__(self, conn) -> None:
        if not self.validator:
            return
        try:
            mtime = os.stat(self.path).st_mtime_ns
        except OSError:
            return
        if mtime == self.mtime:
            return
        with self._lock:
            if mtime == self.mtime:
                return
            self.mtime = mtime  # un fichier en erreur n'est retenté qu'à sa prochaine modification
            from tools.import_gold import import_gold  # l'outil de la ligne de commande, rejoué tel quel
            try:
                report = import_gold(conn, self.path, self.validator, self.lang)
            except Exception as e:  # CSV en cours d'écriture ou mal formé : l'ancienne mémoire reste en place
                log.error("gold non rechargé (%s) : la mémoire précédente est gardée", type(e).__name__)
                return
            # identifiants et raisons seulement, jamais de texte
            refused = " ".join(f"{r['id']}:{r['reason']}" for r in report["refused"])
            log.info("gold rechargé : %s lignes, %s entrées, %s conflits, refusées : %s",
                     report["rows"], report["entries"], len(report["conflicts"]), refused or "aucune")
