"""Stockage local (SQLite). Un seul fichier, sauvegardable en un clic."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

from .calculs import Parametres, Entree, generer_versements, taxes

SCHEMA = """
CREATE TABLE IF NOT EXISTS parametres (cle TEXT PRIMARY KEY, valeur TEXT);
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    telephone TEXT DEFAULT '',
    courriel TEXT DEFAULT '',
    adresse TEXT DEFAULT '',
    ville TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    cree_le TEXT
);
CREATE TABLE IF NOT EXISTS contrats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    saison TEXT NOT NULL,
    entree_json TEXT NOT NULL,
    minutes_visite REAL DEFAULT 0,
    prix REAL NOT NULL,
    tps REAL DEFAULT 0,
    tvq REAL DEFAULT 0,
    total REAL NOT NULL,
    statut TEXT DEFAULT 'Soumission',
    ordre_route INTEGER DEFAULT 0,
    signe_le TEXT,
    cree_le TEXT
);
CREATE TABLE IF NOT EXISTS versements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contrat_id INTEGER NOT NULL REFERENCES contrats(id) ON DELETE CASCADE,
    no INTEGER DEFAULT 1,
    echeance TEXT NOT NULL,
    montant REAL NOT NULL,
    paye INTEGER DEFAULT 0,
    date_paiement TEXT,
    mode TEXT DEFAULT '',
    libelle TEXT DEFAULT '',
    tempete_id INTEGER
);
CREATE TABLE IF NOT EXISTS tempetes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    saison TEXT NOT NULL,
    date TEXT NOT NULL,
    cm REAL DEFAULT 0,
    heures REAL DEFAULT 0,
    notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS depenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    saison TEXT NOT NULL,
    date TEXT NOT NULL,
    categorie TEXT DEFAULT '',
    description TEXT DEFAULT '',
    montant REAL NOT NULL
);
"""

STATUTS = ["Soumission", "Signé", "Annulé"]
CATEGORIES_DEPENSES = ["Carburant", "Entretien / réparation", "Abrasif", "Assurance",
                       "Salaires", "Équipement", "Publicité", "Piquets / balisage", "Autre"]
MODES_PAIEMENT = ["Virement Interac", "Comptant", "Chèque", "Carte", "Autre"]


def dossier_donnees() -> Path:
    if os.environ.get("POUDREUSE_DATA"):
        d = Path(os.environ["POUDREUSE_DATA"])
    elif sys.platform == "win32":
        d = Path(os.environ.get("APPDATA", Path.home())) / "Poudreuse"
    elif sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "Poudreuse"
    else:
        d = Path.home() / ".poudreuse"
    d.mkdir(parents=True, exist_ok=True)
    return d


class Base:
    def __init__(self, chemin: str | Path | None = None):
        self.chemin = Path(chemin) if chemin else dossier_donnees() / "poudreuse.db"
        self.cx = sqlite3.connect(self.chemin)
        self.cx.row_factory = sqlite3.Row
        self.cx.execute("PRAGMA foreign_keys = ON")
        self.cx.executescript(SCHEMA)
        self._migrer()
        self.cx.commit()

    def _migrer(self) -> None:
        cols = {r[1] for r in self.cx.execute("PRAGMA table_info(versements)")}
        if "libelle" not in cols:
            self.cx.execute("ALTER TABLE versements ADD COLUMN libelle TEXT DEFAULT ''")
        if "tempete_id" not in cols:
            self.cx.execute("ALTER TABLE versements ADD COLUMN tempete_id INTEGER")

    @staticmethod
    def _a_la_visite(entree_json: str) -> bool:
        from .calculs import TYPES_CONTRAT
        return json.loads(entree_json).get("type_contrat") == TYPES_CONTRAT[2]

    # ------------------------------------------------------------ paramètres
    def parametres(self) -> Parametres:
        rows = self.cx.execute("SELECT cle, valeur FROM parametres").fetchall()
        return Parametres.from_dict({r["cle"]: json.loads(r["valeur"]) for r in rows})

    def enregistrer_parametres(self, p: Parametres) -> None:
        with self.cx:
            for k, v in p.to_dict().items():
                self.cx.execute("INSERT OR REPLACE INTO parametres VALUES (?, ?)", (k, json.dumps(v)))

    # ------------------------------------------------------------ clients
    def ajouter_client(self, nom, telephone="", courriel="", adresse="", ville="", notes="") -> int:
        with self.cx:
            cur = self.cx.execute(
                "INSERT INTO clients (nom, telephone, courriel, adresse, ville, notes, cree_le) VALUES (?,?,?,?,?,?,?)",
                (nom, telephone, courriel, adresse, ville, notes, datetime.now().isoformat(timespec="seconds")))
        return cur.lastrowid

    def modifier_client(self, cid: int, **champs) -> None:
        permis = {"nom", "telephone", "courriel", "adresse", "ville", "notes"}
        champs = {k: v for k, v in champs.items() if k in permis}
        if not champs:
            return
        sets = ", ".join(f"{k} = ?" for k in champs)
        with self.cx:
            self.cx.execute(f"UPDATE clients SET {sets} WHERE id = ?", (*champs.values(), cid))

    def client(self, cid: int) -> sqlite3.Row | None:
        return self.cx.execute("SELECT * FROM clients WHERE id = ?", (cid,)).fetchone()

    # ------------------------------------------------------------ contrats
    def enregistrer_contrat(self, client_id: int, saison: str, entree: Entree, minutes: float,
                            prix: float, inscrit_taxes: bool, contrat_id: int | None = None) -> int:
        tps, tvq, total = taxes(prix, inscrit_taxes)
        maintenant = datetime.now().isoformat(timespec="seconds")
        with self.cx:
            if contrat_id:
                self.cx.execute(
                    "UPDATE contrats SET client_id=?, saison=?, entree_json=?, minutes_visite=?, prix=?, tps=?, tvq=?, total=? WHERE id=?",
                    (client_id, saison, json.dumps(entree.to_dict()), minutes, prix, tps, tvq, total, contrat_id))
                # les versements non payés sont recalculés
                deja = self.cx.execute("SELECT COALESCE(SUM(montant),0) FROM versements WHERE contrat_id=? AND paye=1",
                                       (contrat_id,)).fetchone()[0]
                statut = self.cx.execute("SELECT statut FROM contrats WHERE id=?", (contrat_id,)).fetchone()[0]
                if self._a_la_visite(json.dumps(entree.to_dict())):
                    self.cx.execute("DELETE FROM versements WHERE contrat_id=? AND paye=0 AND tempete_id IS NULL",
                                    (contrat_id,))
                elif statut == "Signé":
                    self._regenerer_versements(contrat_id, total - deja, entree.nb_versements, saison, garder_payes=True)
                return contrat_id
            ordre = self.cx.execute("SELECT COALESCE(MAX(ordre_route),0)+1 FROM contrats").fetchone()[0]
            cur = self.cx.execute(
                "INSERT INTO contrats (client_id, saison, entree_json, minutes_visite, prix, tps, tvq, total, statut, ordre_route, cree_le)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (client_id, saison, json.dumps(entree.to_dict()), minutes, prix, tps, tvq, total, "Soumission", ordre, maintenant))
        return cur.lastrowid

    def _regenerer_versements(self, contrat_id: int, reste: float, nb: int, saison: str, garder_payes: bool) -> None:
        if garder_payes:
            self.cx.execute("DELETE FROM versements WHERE contrat_id=? AND paye=0", (contrat_id,))
            nb_payes = self.cx.execute("SELECT COUNT(*) FROM versements WHERE contrat_id=?", (contrat_id,)).fetchone()[0]
        else:
            self.cx.execute("DELETE FROM versements WHERE contrat_id=?", (contrat_id,))
            nb_payes = 0
        nb_restants = max(1, nb - nb_payes)
        if reste <= 0.004:
            return
        for i, (ech, mnt) in enumerate(generer_versements(reste, nb_restants, saison), start=nb_payes + 1):
            self.cx.execute("INSERT INTO versements (contrat_id, no, echeance, montant) VALUES (?,?,?,?)",
                            (contrat_id, i, ech.isoformat(), mnt))

    def changer_statut(self, contrat_id: int, statut: str) -> None:
        c = self.contrat(contrat_id)
        if not c:
            return
        with self.cx:
            if statut == "Signé" and c["statut"] != "Signé":
                self.cx.execute("UPDATE contrats SET statut=?, signe_le=? WHERE id=?",
                                (statut, date.today().isoformat(), contrat_id))
                if not self._a_la_visite(c["entree_json"]):
                    entree = Entree.from_dict(json.loads(c["entree_json"]))
                    deja = self.cx.execute("SELECT COALESCE(SUM(montant),0) FROM versements WHERE contrat_id=? AND paye=1",
                                           (contrat_id,)).fetchone()[0]
                    self._regenerer_versements(contrat_id, c["total"] - deja, entree.nb_versements, c["saison"], True)
            else:
                self.cx.execute("UPDATE contrats SET statut=? WHERE id=?", (statut, contrat_id))
                if statut != "Signé":
                    self.cx.execute("DELETE FROM versements WHERE contrat_id=? AND paye=0", (contrat_id,))

    def supprimer_contrat(self, contrat_id: int) -> None:
        with self.cx:
            cid = self.cx.execute("SELECT client_id FROM contrats WHERE id=?", (contrat_id,)).fetchone()
            self.cx.execute("DELETE FROM contrats WHERE id=?", (contrat_id,))
            if cid:
                reste = self.cx.execute("SELECT COUNT(*) FROM contrats WHERE client_id=?", (cid[0],)).fetchone()[0]
                if not reste:
                    self.cx.execute("DELETE FROM clients WHERE id=?", (cid[0],))

    def contrat(self, contrat_id: int) -> sqlite3.Row | None:
        return self.cx.execute(
            "SELECT c.*, cl.nom, cl.telephone, cl.courriel, cl.adresse, cl.ville, cl.notes "
            "FROM contrats c JOIN clients cl ON cl.id = c.client_id WHERE c.id = ?", (contrat_id,)).fetchone()

    def contrats(self, saison: str | None = None, statut: str | None = None, recherche: str = "") -> list[sqlite3.Row]:
        sql = ("SELECT c.*, cl.nom, cl.telephone, cl.courriel, cl.adresse, cl.ville, cl.notes, "
               "COALESCE((SELECT SUM(montant) FROM versements v WHERE v.contrat_id=c.id AND v.paye=1),0) AS paye, "
               "COALESCE((SELECT SUM(montant) FROM versements v WHERE v.contrat_id=c.id),0) AS facture "
               "FROM contrats c JOIN clients cl ON cl.id = c.client_id WHERE 1=1")
        args: list = []
        if saison:
            sql += " AND c.saison = ?"
            args.append(saison)
        if statut:
            sql += " AND c.statut = ?"
            args.append(statut)
        if recherche:
            sql += " AND (cl.nom LIKE ? OR cl.adresse LIKE ? OR cl.ville LIKE ? OR cl.telephone LIKE ?)"
            args += [f"%{recherche}%"] * 4
        sql += " ORDER BY c.ordre_route, c.id"
        return self.cx.execute(sql, args).fetchall()

    def deplacer_route(self, contrat_id: int, direction: int, saison: str) -> None:
        liste = [r["id"] for r in self.contrats(saison, "Signé")]
        if contrat_id not in liste:
            return
        i = liste.index(contrat_id)
        j = i + direction
        if not 0 <= j < len(liste):
            return
        liste[i], liste[j] = liste[j], liste[i]
        with self.cx:
            for n, cid in enumerate(liste, start=1):
                self.cx.execute("UPDATE contrats SET ordre_route=? WHERE id=?", (n, cid))

    # ------------------------------------------------------------ versements
    def versements(self, saison: str | None = None) -> list[sqlite3.Row]:
        sql = ("SELECT v.*, c.saison, c.total AS total_contrat, cl.nom, cl.adresse, cl.telephone, cl.courriel, c.id AS cid "
               "FROM versements v JOIN contrats c ON c.id=v.contrat_id JOIN clients cl ON cl.id=c.client_id")
        args = []
        if saison:
            sql += " WHERE c.saison = ?"
            args.append(saison)
        sql += " ORDER BY v.paye, v.echeance, cl.nom"
        return self.cx.execute(sql, args).fetchall()

    def versements_contrat(self, contrat_id: int) -> list[sqlite3.Row]:
        return self.cx.execute("SELECT * FROM versements WHERE contrat_id=? ORDER BY no", (contrat_id,)).fetchall()

    def marquer_paye(self, vid: int, paye: bool, mode: str = "", quand: date | None = None) -> None:
        with self.cx:
            if paye:
                self.cx.execute("UPDATE versements SET paye=1, date_paiement=?, mode=? WHERE id=?",
                                ((quand or date.today()).isoformat(), mode, vid))
            else:
                self.cx.execute("UPDATE versements SET paye=0, date_paiement=NULL, mode='' WHERE id=?", (vid,))

    def versement(self, vid: int) -> sqlite3.Row | None:
        return self.cx.execute(
            "SELECT v.*, c.saison, cl.nom, cl.adresse, cl.ville, cl.courriel, c.id AS cid FROM versements v "
            "JOIN contrats c ON c.id=v.contrat_id JOIN clients cl ON cl.id=c.client_id WHERE v.id=?", (vid,)).fetchone()

    # ------------------------------------------------------------ tempêtes et dépenses
    def ajouter_tempete(self, saison, quand: str, cm: float, heures: float, notes: str = "",
                        facturer_visites: bool = True) -> int:
        """Ajoute une tempête. Les clients signés « à la visite » reçoivent automatiquement une facture."""
        with self.cx:
            cur = self.cx.execute("INSERT INTO tempetes (saison, date, cm, heures, notes) VALUES (?,?,?,?,?)",
                                  (saison, quand, cm, heures, notes))
            tid = cur.lastrowid
            if facturer_visites:
                for c in self.cx.execute("SELECT id, total, entree_json FROM contrats WHERE saison=? AND statut='Signé'",
                                         (saison,)).fetchall():
                    if self._a_la_visite(c["entree_json"]):
                        no = self.cx.execute("SELECT COALESCE(MAX(no),0)+1 FROM versements WHERE contrat_id=?",
                                             (c["id"],)).fetchone()[0]
                        self.cx.execute("INSERT INTO versements (contrat_id, no, echeance, montant, libelle, tempete_id) "
                                        "VALUES (?,?,?,?,?,?)", (c["id"], no, quand, c["total"], "Visite", tid))
        return tid

    def nb_visites_facturees(self, saison) -> int:
        return self.cx.execute("SELECT COUNT(*) FROM versements v JOIN contrats c ON c.id=v.contrat_id "
                               "WHERE c.saison=? AND v.tempete_id IS NOT NULL", (saison,)).fetchone()[0]

    def tempetes(self, saison) -> list[sqlite3.Row]:
        return self.cx.execute("SELECT * FROM tempetes WHERE saison=? ORDER BY date DESC", (saison,)).fetchall()

    def ajouter_depense(self, saison, quand: str, categorie: str, description: str, montant: float) -> None:
        with self.cx:
            self.cx.execute("INSERT INTO depenses (saison, date, categorie, description, montant) VALUES (?,?,?,?,?)",
                            (saison, quand, categorie, description, montant))

    def depenses(self, saison) -> list[sqlite3.Row]:
        return self.cx.execute("SELECT * FROM depenses WHERE saison=? ORDER BY date DESC", (saison,)).fetchall()

    def supprimer(self, table: str, rid: int) -> None:
        if table not in ("tempetes", "depenses"):
            raise ValueError(table)
        with self.cx:
            if table == "tempetes":
                self.cx.execute("DELETE FROM versements WHERE tempete_id=? AND paye=0", (rid,))
            self.cx.execute(f"DELETE FROM {table} WHERE id=?", (rid,))

    def saisons(self) -> list[str]:
        rows = self.cx.execute("SELECT DISTINCT saison FROM contrats UNION SELECT DISTINCT saison FROM tempetes "
                               "UNION SELECT DISTINCT saison FROM depenses ORDER BY 1 DESC").fetchall()
        return [r[0] for r in rows]

    # ------------------------------------------------------------ résumé
    def resume(self, saison: str) -> dict:
        q = self.cx.execute
        rangs = q("SELECT prix, total, entree_json FROM contrats WHERE saison=? AND statut='Signé'", (saison,)).fetchall()
        saisonniers = [r for r in rangs if not self._a_la_visite(r["entree_json"])]
        signes = (len(rangs), sum(r["prix"] for r in saisonniers), sum(r["total"] for r in saisonniers))
        soum = q("SELECT COUNT(*), COALESCE(SUM(prix),0) FROM contrats WHERE saison=? AND statut='Soumission'", (saison,)).fetchone()
        encaisse = q("SELECT COALESCE(SUM(v.montant),0) FROM versements v JOIN contrats c ON c.id=v.contrat_id "
                     "WHERE c.saison=? AND v.paye=1", (saison,)).fetchone()[0]
        a_recevoir = q("SELECT COALESCE(SUM(v.montant),0) FROM versements v JOIN contrats c ON c.id=v.contrat_id "
                       "WHERE c.saison=? AND v.paye=0 AND c.statut='Signé'", (saison,)).fetchone()[0]
        en_retard = q("SELECT COUNT(*), COALESCE(SUM(v.montant),0) FROM versements v JOIN contrats c ON c.id=v.contrat_id "
                      "WHERE c.saison=? AND v.paye=0 AND c.statut='Signé' AND v.echeance < ?",
                      (saison, date.today().isoformat())).fetchone()
        dep = q("SELECT COALESCE(SUM(montant),0) FROM depenses WHERE saison=?", (saison,)).fetchone()[0]
        temp = q("SELECT COUNT(*), COALESCE(SUM(cm),0), COALESCE(SUM(heures),0) FROM tempetes WHERE saison=?",
                 (saison,)).fetchone()
        return dict(
            nb_signes=signes[0], revenus=signes[1], revenus_ttc=signes[2],
            nb_soumissions=soum[0], valeur_soumissions=soum[1],
            encaisse=encaisse, a_recevoir=a_recevoir,
            nb_retard=en_retard[0], montant_retard=en_retard[1],
            depenses=dep, nb_tempetes=temp[0], cm_total=temp[1], heures_total=temp[2],
        )

    # ------------------------------------------------------------ sauvegarde
    def sauvegarder_vers(self, destination: str | Path) -> None:
        self.cx.commit()
        dest = sqlite3.connect(destination)
        with dest:
            self.cx.backup(dest)
        dest.close()

    def restaurer_depuis(self, source: str | Path) -> None:
        test = sqlite3.connect(source)
        try:
            test.execute("SELECT COUNT(*) FROM contrats").fetchone()
        finally:
            test.close()
        self.cx.close()
        shutil.copyfile(source, self.chemin)
        self.__init__(self.chemin)

    def exporter_csv(self, destination: str | Path, saison: str) -> None:
        import csv
        with open(destination, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Client", "Téléphone", "Courriel", "Adresse", "Ville", "Statut",
                        "Prix avant taxes", "TPS", "TVQ", "Total", "Payé", "Solde"])
            for r in self.contrats(saison):
                du = r["facture"] if self._a_la_visite(r["entree_json"]) else r["total"]
                w.writerow([r["nom"], r["telephone"], r["courriel"], r["adresse"], r["ville"], r["statut"],
                            f"{r['prix']:.2f}".replace(".", ","), f"{r['tps']:.2f}".replace(".", ","),
                            f"{r['tvq']:.2f}".replace(".", ","), f"{r['total']:.2f}".replace(".", ","),
                            f"{r['paye']:.2f}".replace(".", ","), f"{(du - r['paye']) if r['statut'] == 'Signé' else 0:.2f}".replace(".", ",")])
