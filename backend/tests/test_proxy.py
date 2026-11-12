"""Audit 1 et 5 : adresse réelle derrière un proxy (ProxyFix désactivé par défaut) ; réseaux admin validés au démarrage."""
import pytest

from amira import create_app
from conftest import DEV

TOKEN = {"Authorization": "Bearer jeton"}
PROXY = {"REMOTE_ADDR": "10.0.0.2"}  # passerelle de la banque, sur le réseau interne


def body():
    return {"requestId": "r", "source": "fr", "target": "ff", "variety": "ngaoundere",
            "segments": [{"id": "a", "text": "Bonjour", "placeholders": []}]}


def make(db_path, **env):
    return create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ADMIN_TOKENS": "jeton", **env}, engine=None)


def test_sans_variable_x_forwarded_for_ignore(db_path):
    c = make(db_path).test_client()
    # un client externe qui forge l'en-tête ne se fait pas passer pour une adresse interne
    r = c.get("/v1/admin/feedback", headers={**TOKEN, "X-Forwarded-For": "10.0.0.5"}, environ_base={"REMOTE_ADDR": "8.8.8.8"})
    assert r.status_code == 401


def test_sans_variable_limiteur_sur_l_adresse_reelle(db_path):
    c = make(db_path, AMIRA_RATE_LIMIT_PER_MIN="2").test_client()
    codes = [c.post("/v1/translate", json=body(), headers={"X-Forwarded-For": f"8.8.8.{i}"}, environ_base=PROXY).status_code
             for i in range(3)]
    assert codes == [200, 200, 429]  # l'en-tête forgé ne crée pas de nouveaux quotas


def test_avec_proxy_de_confiance_adresse_du_client(db_path):
    c = make(db_path, AMIRA_TRUSTED_PROXIES="1").test_client()
    # le proxy relaie un client externe : l'admin le refuse malgré l'adresse interne du proxy
    r = c.get("/v1/admin/feedback", headers={**TOKEN, "X-Forwarded-For": "8.8.8.8"}, environ_base=PROXY)
    assert r.status_code == 401
    r = c.get("/v1/admin/feedback", headers={**TOKEN, "X-Forwarded-For": "10.0.0.7"}, environ_base=PROXY)
    assert r.status_code == 200


def test_avec_proxy_seule_l_adresse_ajoutee_par_le_proxy_compte(db_path):
    c = make(db_path, AMIRA_TRUSTED_PROXIES="1").test_client()
    # le client forge « 10.0.0.5 » ; le proxy de confiance ajoute la vraie adresse à la fin
    r = c.get("/v1/admin/feedback", headers={**TOKEN, "X-Forwarded-For": "10.0.0.5, 8.8.8.8"}, environ_base=PROXY)
    assert r.status_code == 401


def test_avec_proxy_limiteur_par_client(db_path):
    c = make(db_path, AMIRA_TRUSTED_PROXIES="1", AMIRA_RATE_LIMIT_PER_MIN="2").test_client()
    send = lambda ip: c.post("/v1/translate", json=body(), headers={"X-Forwarded-For": ip}, environ_base=PROXY).status_code
    assert [send("8.8.8.1"), send("8.8.8.1"), send("8.8.8.1")] == [200, 200, 429]
    assert send("8.8.8.2") == 200  # un autre client garde son quota


@pytest.mark.parametrize("value", ["-1", "x", "1.5"])
def test_nombre_de_proxys_invalide(db_path, value):
    with pytest.raises((RuntimeError, ValueError)):
        make(db_path, AMIRA_TRUSTED_PROXIES=value)


@pytest.mark.parametrize("networks", ["10.0.0/8", "10.0.0.0/33", "localhost", "127.0.0.1/8,abc"])
def test_reseaux_admin_valides_au_demarrage(db_path, networks):
    with pytest.raises(RuntimeError, match="AMIRA_ADMIN_NETWORKS"):
        make(db_path, AMIRA_ADMIN_NETWORKS=networks)


def test_reseau_admin_ipv6(db_path):
    c = make(db_path, AMIRA_ADMIN_NETWORKS="::1/128").test_client()
    assert c.get("/v1/admin/feedback", headers=TOKEN, environ_base={"REMOTE_ADDR": "::1"}).status_code == 200
    assert c.get("/v1/admin/feedback", headers=TOKEN).status_code == 401  # 127.0.0.1 n'est plus dans la liste
