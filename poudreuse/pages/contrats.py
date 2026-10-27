"""Page Clients et contrats."""
from __future__ import annotations

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QPushButton, QMessageBox,
                               QFileDialog)

from ..calculs import argent
from ..donnees import STATUTS, Base
from ..theme import EPINETTE, BALISE, GRIS
from ..widgets import entete_page, tableau, item, ItemNum, id_selection, etiquette

COULEUR_STATUT = {"Signé": EPINETTE, "Soumission": GRIS, "Annulé": BALISE}


class PageContrats(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)
        lay.addWidget(entete_page("Clients et contrats",
                                  "Double-cliquez sur une ligne pour ouvrir le contrat et le modifier."))

        barre = QHBoxLayout()
        self.recherche = QLineEdit(placeholderText="Chercher un nom, une adresse ou un téléphone")
        self.recherche.setClearButtonEnabled(True)
        self.filtre = QComboBox()
        self.filtre.addItems(["Tous les statuts"] + STATUTS)
        barre.addWidget(self.recherche, 1)
        barre.addWidget(self.filtre)
        self.resume = etiquette("", "aide")
        barre.addWidget(self.resume)
        lay.addLayout(barre)

        self.t = tableau(["Client", "Adresse", "Téléphone", "Statut", "Avant taxes", "Total", "Payé", "Solde"], etirer=1)
        self.t.setSortingEnabled(True)
        lay.addWidget(self.t, 1)

        actions = QHBoxLayout()
        self.b_ouvrir = QPushButton("Ouvrir")
        self.b_signer = QPushButton("Marquer comme signé")
        self.b_signer.setObjectName("principal")
        self.b_soum = QPushButton("Remettre en soumission")
        self.b_annuler = QPushButton("Annuler le contrat")
        self.b_pdf = QPushButton("Créer le PDF")
        self.b_csv = QPushButton("Exporter en CSV")
        self.b_suppr = QPushButton("Supprimer")
        self.b_suppr.setObjectName("danger")
        for b in (self.b_ouvrir, self.b_signer, self.b_soum, self.b_annuler, self.b_pdf):
            actions.addWidget(b)
        actions.addStretch()
        actions.addWidget(self.b_csv)
        actions.addWidget(self.b_suppr)
        lay.addLayout(actions)

        self.recherche.textChanged.connect(self.rafraichir)
        self.filtre.currentIndexChanged.connect(self.rafraichir)
        self.t.itemSelectionChanged.connect(self._etat_boutons)
        self.t.cellDoubleClicked.connect(lambda *_: self._ouvrir())
        self.b_ouvrir.clicked.connect(self._ouvrir)
        self.b_signer.clicked.connect(lambda: self._statut("Signé"))
        self.b_soum.clicked.connect(lambda: self._statut("Soumission"))
        self.b_annuler.clicked.connect(lambda: self._statut("Annulé"))
        self.b_pdf.clicked.connect(self._pdf)
        self.b_csv.clicked.connect(self._csv)
        self.b_suppr.clicked.connect(self._supprimer)

    def rafraichir(self, *_):
        statut = self.filtre.currentText() if self.filtre.currentIndex() > 0 else None
        rangs = self.app.db.contrats(self.app.saison, statut, self.recherche.text().strip())
        self.t.setSortingEnabled(False)
        self.t.setRowCount(len(rangs))
        total = 0.0
        for i, r in enumerate(rangs):
            visite = Base._a_la_visite(r["entree_json"])
            du = r["facture"] if visite else r["total"]
            solde = du - r["paye"] if r["statut"] == "Signé" else 0
            adresse = ", ".join(x for x in (r["adresse"], r["ville"]) if x)
            self.t.setItem(i, 0, item(r["nom"], r["id"], gras=True))
            self.t.setItem(i, 1, item(adresse))
            self.t.setItem(i, 2, item(r["telephone"]))
            self.t.setItem(i, 3, item(r["statut"], couleur=COULEUR_STATUT.get(r["statut"])))
            suffixe = " / visite" if visite else ""
            self.t.setItem(i, 4, ItemNum(r["prix"], argent(r["prix"]) + suffixe))
            self.t.setItem(i, 5, ItemNum(r["total"], argent(r["total"]) + suffixe))
            self.t.setItem(i, 6, ItemNum(r["paye"]))
            self.t.setItem(i, 7, ItemNum(solde))
            if r["statut"] == "Signé" and not visite:
                total += r["prix"]
        self.t.setSortingEnabled(True)
        n = sum(1 for r in rangs if r["statut"] == "Signé")
        self.resume.setText(f"{len(rangs)} contrat{'s' * (len(rangs) > 1)}, dont {n} signé{'s' * (n > 1)} ({argent(total)})")
        self._etat_boutons()

    def _etat_boutons(self):
        cid = id_selection(self.t)
        c = self.app.db.contrat(cid) if cid else None
        for b in (self.b_ouvrir, self.b_pdf, self.b_suppr):
            b.setEnabled(c is not None)
        self.b_signer.setEnabled(bool(c) and c["statut"] != "Signé")
        self.b_soum.setEnabled(bool(c) and c["statut"] != "Soumission")
        self.b_annuler.setEnabled(bool(c) and c["statut"] != "Annulé")

    def _ouvrir(self):
        cid = id_selection(self.t)
        if cid:
            self.app.ouvrir_contrat(cid)

    def _statut(self, statut: str):
        cid = id_selection(self.t)
        if not cid:
            return
        c = self.app.db.contrat(cid)
        if statut != "Signé" and c["statut"] == "Signé":
            if QMessageBox.question(self, "Changer le statut",
                                    f"Les versements non payés de {c['nom']} seront retirés. Continuer ?") != QMessageBox.StandardButton.Yes:
                return
        self.app.db.changer_statut(cid, statut)
        self.app.rafraichir()
        self.app.toast({"Signé": f"Contrat de {c['nom']} signé. Les versements sont créés.",
                        "Annulé": "Contrat annulé.", "Soumission": "Remis en soumission."}[statut])

    def _pdf(self):
        cid = id_selection(self.t)
        if cid:
            self.app.pdf_contrat(cid)

    def _csv(self):
        chemin, _ = QFileDialog.getSaveFileName(self, "Exporter les contrats",
                                                str(self.app.dossier_documents() / f"contrats-{self.app.saison}.csv"),
                                                "Fichier CSV (*.csv)")
        if chemin:
            self.app.db.exporter_csv(chemin, self.app.saison)
            self.app.toast("Contrats exportés. Le fichier s'ouvre dans Excel.")

    def _supprimer(self):
        cid = id_selection(self.t)
        if not cid:
            return
        c = self.app.db.contrat(cid)
        if QMessageBox.question(self, "Supprimer le contrat",
                                f"Supprimer définitivement le contrat de {c['nom']} et ses paiements ?") == QMessageBox.StandardButton.Yes:
            self.app.db.supprimer_contrat(cid)
            self.app.rafraichir()
            self.app.toast("Contrat supprimé.")
