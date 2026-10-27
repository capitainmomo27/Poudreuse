"""Remplit une base avec des données de démonstration réalistes (pour essayer le logiciel ou faire des captures)."""
from __future__ import annotations

import random
from datetime import date, timedelta

from .calculs import Entree, TYPES_CONTRAT, calculer, saison_courante
from .donnees import Base

NOMS = ["Marie Tremblay", "Jean-François Gagnon", "Sophie Roy", "Luc Côté", "Isabelle Bouchard", "Marc Gauthier",
        "Nathalie Morin", "Patrick Lavoie", "Julie Fortin", "Éric Gagné", "Chantal Ouellet", "Michel Pelletier",
        "Annie Bélanger", "Stéphane Lévesque", "Caroline Bergeron", "Daniel Leblanc", "Mélanie Paquette",
        "Sylvain Girard", "Geneviève Simard", "François Boucher", "Karine Caron", "Martin Beaulieu"]
RUES = ["rue des Érables", "boul. Saint-Martin", "rue Principale", "rue des Pins", "av. du Parc", "rue Lafontaine",
        "montée Masson", "rue Notre-Dame", "rue des Lilas", "rue Cartier"]


def remplir(db: Base, saison: str | None = None, graine: int = 7, garder_entreprise: bool = False) -> None:
    rnd = random.Random(graine)
    p = db.parametres()
    if garder_entreprise and p.nom_entreprise != "Mon entreprise de déneigement":
        saison = saison or p.saison or saison_courante()
    else:
        p.nom_entreprise = "Déneigement Boréal"
        p.telephone = "450 555-0199"
        p.courriel = "info@deneigementboreal.ca"
        p.adresse = "1280, montée Masson"
        p.ville = "Laval (Québec) H7E 4P2"
        p.neq = "1174829301"
        p.no_tps = "784512369 RT0001"
        p.no_tvq = "1225478963 TQ0001"
        saison = saison or saison_courante()
        p.saison = saison
        db.enregistrer_parametres(p)
    debut = int(saison[:4])
    for i, nom in enumerate(NOMS):
        cid = db.ajouter_client(nom, f"514 555-{1000 + i * 37:04d}", f"{nom.split()[0].lower()}@exemple.com",
                                f"{rnd.randint(100, 4999)}, {rnd.choice(RUES)}", "Laval")
        e = Entree(longueur_pi=rnd.choice([30, 40, 40, 50, 60, 80]), largeur_pi=rnd.choice([10, 12, 20, 20, 24]),
                   methode=rnd.choice(["Pick-up avec gratte"] * 4 + ["Tracteur avec souffleuse"]),
                   trottoir_pi=rnd.choice([0, 0, 0, 25, 40]), perrons=rnd.choice([0, 0, 1, 2]),
                   abrasif=rnd.random() < 0.3, nb_versements=rnd.choice([1, 2, 2, 3]),
                   type_contrat=TYPES_CONTRAT[0] if rnd.random() < 0.9 else TYPES_CONTRAT[2])
        r = calculer(e, p)
        kid = db.enregistrer_contrat(cid, saison, e, r.minutes_visite, r.prix, p.inscrit_taxes)
        if i < 17:
            db.changer_statut(kid, "Signé")
            vs = db.versements_contrat(kid)
            if vs and i % 5 != 4:
                db.marquer_paye(vs[0]["id"], True, rnd.choice(["Virement Interac", "Comptant", "Chèque"]),
                                date(debut, 10, rnd.randint(1, 25)))
        elif i == 21:
            db.changer_statut(kid, "Annulé")
    # quelques versements passés en retard pour la démonstration
    with db.cx:
        db.cx.execute("UPDATE versements SET echeance=? WHERE no=1 AND paye=0", (date(debut, 10, 15).isoformat(),))
    for d, cm, h in [(date(debut, 11, 18), 12, 5.5), (date(debut, 11, 27), 22, 8.0), (date(debut, 12, 4), 8, 4.0)]:
        if d <= date.today() + timedelta(days=60):
            db.ajouter_tempete(saison, d.isoformat(), cm, h, "")
    for d, cat, desc, m in [(date(debut, 9, 20), "Assurance", "Responsabilité civile", 1450),
                            (date(debut, 10, 5), "Piquets / balisage", "300 piquets orange", 285),
                            (date(debut, 10, 12), "Entretien / réparation", "Lame de gratte et huile", 640),
                            (date(debut, 10, 22), "Publicité", "Accroche-portes", 180),
                            (date(debut, 11, 18), "Carburant", "Plein du pick-up", 132)]:
        db.ajouter_depense(saison, d.isoformat(), cat, desc, m)


