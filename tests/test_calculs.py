from datetime import date

import pytest

from poudreuse.calculs import (Entree, Parametres, TYPES_CONTRAT, calculer, taxes, arrondi_vente,
                               generer_versements, rentabilite_saison, argent, saison_courante)
from poudreuse.donnees import Base


def test_taxes_quebec():
    tps, tvq, total = taxes(100.0)
    assert tps == 5.00
    assert tvq == 9.98          # 9,975 arrondi
    assert total == 114.98


def test_taxes_petit_fournisseur():
    assert taxes(500, inscrit=False) == (0.0, 0.0, 500.0)


def test_arrondi_vente():
    assert arrondi_vente(440.12) == 445
    assert arrondi_vente(445) == 445
    assert arrondi_vente(0) == 0


def test_prix_entree_standard_realiste():
    r = calculer(Entree(), Parametres())
    # Une entrée double de 40 x 20 pi au pick-up : entre 350 $ et 900 $ au Québec
    assert 350 <= r.prix <= 900
    assert r.prix % 5 == 0
    assert 0.25 < r.marge_reelle < 0.35
    assert r.total == pytest.approx(r.prix * 1.14975, abs=0.02)


def test_plus_grande_entree_coute_plus():
    p = Parametres()
    petite = calculer(Entree(longueur_pi=20, largeur_pi=10), p)
    grande = calculer(Entree(longueur_pi=80, largeur_pi=24), p)
    assert grande.prix > petite.prix


def test_pelle_plus_lente_que_tracteur():
    p = Parametres()
    a = calculer(Entree(methode="Pelle (à la main)"), p)
    b = calculer(Entree(methode="Tracteur avec souffleuse"), p)
    assert a.minutes_visite > b.minutes_visite


def test_options_augmentent_le_prix():
    p = Parametres()
    base = calculer(Entree(), p)
    plus = calculer(Entree(trottoir_pi=60, perrons=2, abrasif=True), p)
    assert plus.prix > base.prix


def test_prix_minimum():
    r = calculer(Entree(longueur_pi=10, largeur_pi=8, repasse=False), Parametres(prix_minimum=700))
    assert r.prix == 700


def test_scenarios_hiver_neigeux_moins_rentable():
    r = calculer(Entree(), Parametres())
    leger, normal, neigeux = [s[2] for s in r.scenarios]
    assert leger > normal > neigeux


def test_visites_limitees_plafonnees():
    p = Parametres()
    lim = calculer(Entree(type_contrat=TYPES_CONTRAT[1], visites_incluses=10), p)
    illi = calculer(Entree(type_contrat=TYPES_CONTRAT[0]), p)
    assert lim.visites_prevues == 10
    assert lim.prix < illi.prix


def test_a_la_visite():
    r = calculer(Entree(type_contrat=TYPES_CONTRAT[2]), Parametres())
    assert r.prix == r.prix_par_visite
    assert 30 <= r.prix <= 80


def test_rabais():
    p = Parametres()
    a = calculer(Entree(), p)
    b = calculer(Entree(rabais_pct=10), p)
    assert b.prix == pytest.approx(a.prix * 0.9, abs=0.01)


def test_versements_somme_exacte():
    for nb in (1, 2, 3, 4):
        v = generer_versements(565.73, nb, "2026-2027", date(2026, 10, 27))
        assert len(v) == nb
        assert sum(m for _, m in v) == pytest.approx(565.73, abs=0.001)
        assert v[0][0] == date(2026, 10, 27)
    deux = generer_versements(500, 2, "2026-2027", date(2026, 10, 27))
    assert deux[1][0] == date(2027, 1, 15)


def test_rentabilite():
    p = Parametres(nb_clients_prevus=40)
    contrats = []
    for _ in range(40):
        e = Entree()
        contrats.append({"entree": e, "prix": calculer(e, p).prix})
    r = rentabilite_saison(contrats, p)
    assert r.profit_normal > 0
    assert r.seuil_tempetes > p.tempetes_normales
    assert r.equipes_requises >= 1
    # la courbe descend : plus de neige = moins de profit pour des contrats saisonniers
    assert r.courbe[10][1] > r.courbe[40][1]


def test_format_argent():
    assert argent(1234.5) == "1 234,50 $"
    assert argent(-3) == "-3,00 $"


def test_saison():
    assert saison_courante(date(2026, 10, 27)) == "2026-2027"
    assert saison_courante(date(2027, 2, 1)) == "2026-2027"


def test_base_donnees(tmp_path):
    db = Base(tmp_path / "t.db")
    p = db.parametres()
    p.nom_entreprise = "Déneigement Test"
    db.enregistrer_parametres(p)
    assert db.parametres().nom_entreprise == "Déneigement Test"

    cid = db.ajouter_client("Marie Tremblay", "514-555-0101", adresse="123 rue des Érables", ville="Laval")
    e = Entree(nb_versements=3)
    r = calculer(e, p)
    kid = db.enregistrer_contrat(cid, "2026-2027", e, r.minutes_visite, r.prix, True)
    assert db.versements_contrat(kid) == []
    db.changer_statut(kid, "Signé")
    vs = db.versements_contrat(kid)
    assert len(vs) == 3
    assert sum(v["montant"] for v in vs) == pytest.approx(r.total, abs=0.01)

    db.marquer_paye(vs[0]["id"], True, "Comptant")
    res = db.resume("2026-2027")
    assert res["nb_signes"] == 1
    assert res["encaisse"] == pytest.approx(vs[0]["montant"])

    # modifier le prix garde le paiement déjà reçu
    e2 = Entree(nb_versements=3, perrons=2)
    r2 = calculer(e2, p)
    db.enregistrer_contrat(cid, "2026-2027", e2, r2.minutes_visite, r2.prix, True, contrat_id=kid)
    vs2 = db.versements_contrat(kid)
    assert sum(v["montant"] for v in vs2) == pytest.approx(r2.total, abs=0.01)
    assert vs2[0]["paye"] == 1

    db.ajouter_depense("2026-2027", "2026-11-01", "Carburant", "Plein", 120)
    db.ajouter_tempete("2026-2027", "2026-11-20", 15, 6.5)
    res = db.resume("2026-2027")
    assert res["depenses"] == 120 and res["nb_tempetes"] == 1

    db.exporter_csv(tmp_path / "x.csv", "2026-2027")
    assert "Marie Tremblay" in (tmp_path / "x.csv").read_text(encoding="utf-8-sig")

    db.sauvegarder_vers(tmp_path / "copie.db")
    db.supprimer_contrat(kid)
    assert db.contrats() == []
    db.restaurer_depuis(tmp_path / "copie.db")
    assert len(db.contrats()) == 1


def test_facturation_a_la_visite(tmp_path):
    db = Base(tmp_path / "v.db")
    p = db.parametres()
    cid = db.ajouter_client("Paul Visite")
    e = Entree(type_contrat=TYPES_CONTRAT[2])
    r = calculer(e, p)
    kid = db.enregistrer_contrat(cid, "2026-2027", e, r.minutes_visite, r.prix, True)
    db.changer_statut(kid, "Signé")
    assert db.versements_contrat(kid) == []          # pas d'échéancier pour un contrat à la visite
    tid = db.ajouter_tempete("2026-2027", "2026-12-01", 15, 5)
    db.ajouter_tempete("2026-2027", "2026-12-09", 10, 4)
    vs = db.versements_contrat(kid)
    assert len(vs) == 2 and all(v["libelle"] == "Visite" for v in vs)
    assert vs[0]["montant"] == pytest.approx(r.total)
    db.supprimer("tempetes", tid)
    assert len(db.versements_contrat(kid)) == 1
    assert db.resume("2026-2027")["revenus"] == 0     # les visites ne gonflent pas les revenus saisonniers
    c = db.contrats("2026-2027")[0]
    assert c["facture"] == pytest.approx(r.total)
