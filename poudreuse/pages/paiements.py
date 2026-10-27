"""Page Paiements : qui a payé, qui est en retard."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QDialog, QFormLayout,
                               QDateEdit, QDialogButtonBox, QLineEdit)

from ..calculs import argent
from ..donnees import MODES_PAIEMENT
from ..pdf import date_longue
from ..theme import EPINETTE, BALISE, GRIS
from ..widgets import entete_page, tableau, item, ItemNum, id_selection, BandeKpi

FILTRES = ["À recevoir", "En retard", "Payés", "Tous"]


class DialoguePaiement(QDialog):
    def __init__(self, parent, nom: str, montant: float):
        super().__init__(parent)
        self.setWindowTitle("Enregistrer un paiement")
        self.setMinimumWidth(380)
        f = QFormLayout(self)
        f.setContentsMargins(22, 22, 22, 22)
        f.setSpacing(10)
        f.addRow("Client", QLineEdit(nom, readOnly=True))
        f.addRow("Montant", QLineEdit(argent(montant), readOnly=True))
        self.mode = QComboBox()
        self.mode.addItems(MODES_PAIEMENT)
        f.addRow("Mode", self.mode)
        self.quand = QDateEdit(QDate.currentDate())
        self.quand.setCalendarPopup(True)
        self.quand.setDisplayFormat("d MMMM yyyy")
        f.addRow("Reçu le", self.quand)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        b.button(QDialogButtonBox.StandardButton.Ok).setText("Enregistrer le paiement")
        b.button(QDialogButtonBox.StandardButton.Ok).setObjectName("principal")
        b.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        f.addRow(b)


class PagePaiements(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)
        lay.addWidget(entete_page("Paiements", "Les versements sont créés automatiquement quand un contrat est signé."))

        self.bande = BandeKpi(["Encaissé", "À recevoir", "En retard"])
        lay.addWidget(self.bande)

        barre = QHBoxLayout()
        self.filtre = QComboBox()
        self.filtre.addItems(FILTRES)
        barre.addWidget(self.filtre)
        barre.addStretch()
        lay.addLayout(barre)

        self.t = tableau(["Client", "Adresse", "Versement", "Échéance", "Montant", "État", "Mode"], etirer=1)
        self.t.setSortingEnabled(True)
        lay.addWidget(self.t, 1)

        actions = QHBoxLayout()
        self.b_payer = QPushButton("Enregistrer le paiement")
        self.b_payer.setObjectName("principal")
        self.b_annuler = QPushButton("Annuler ce paiement")
        self.b_recu = QPushButton("Créer le reçu")
        self.b_rappel = QPushButton("Copier un rappel")
        for b in (self.b_payer, self.b_annuler, self.b_recu, self.b_rappel):
            actions.addWidget(b)
        actions.addStretch()
        lay.addLayout(actions)

        self.filtre.currentIndexChanged.connect(self.rafraichir)
        self.t.itemSelectionChanged.connect(self._etat)
        self.t.cellDoubleClicked.connect(lambda *_: self._payer())
        self.b_payer.clicked.connect(self._payer)
        self.b_annuler.clicked.connect(self._annuler)
        self.b_recu.clicked.connect(self._recu)
        self.b_rappel.clicked.connect(self._rappel)

    def rafraichir(self, *_):
        db = self.app.db
        res = db.resume(self.app.saison)
        k = self.bande.kpis
        k[0].definir(argent(res["encaisse"]))
        k[1].definir(argent(res["a_recevoir"]))
        k[2].definir(argent(res["montant_retard"]), alerte=res["montant_retard"] > 0,
                     detail=f"En retard ({res['nb_retard']} versement{'s' * (res['nb_retard'] > 1)})")

        aujourdhui = date.today().isoformat()
        filtre = self.filtre.currentText()
        rangs = []
        nb_par_contrat: dict[int, int] = {}
        for v in db.versements(self.app.saison):
            if not v["libelle"]:
                nb_par_contrat[v["contrat_id"]] = nb_par_contrat.get(v["contrat_id"], 0) + 1
        for v in db.versements(self.app.saison):
            retard = not v["paye"] and v["echeance"] < aujourdhui
            if filtre == "À recevoir" and v["paye"]:
                continue
            if filtre == "En retard" and not retard:
                continue
            if filtre == "Payés" and not v["paye"]:
                continue
            rangs.append((v, retard))

        self.t.setSortingEnabled(False)
        self.t.setRowCount(len(rangs))
        for i, (v, retard) in enumerate(rangs):
            if v["paye"]:
                etat, coul = f"Payé le {date_longue(v['date_paiement'])}", EPINETTE
            elif retard:
                etat, coul = "En retard", BALISE
            else:
                etat, coul = "À venir", GRIS
            self.t.setItem(i, 0, item(v["nom"], v["id"], gras=True))
            self.t.setItem(i, 1, item(v["adresse"]))
            if v["libelle"]:
                self.t.setItem(i, 2, item(v["libelle"]))
            else:
                self.t.setItem(i, 2, item(f"{v['no']} de {nb_par_contrat.get(v['contrat_id'], 1)}"))
            ech = ItemNum(date.fromisoformat(v["echeance"]).toordinal(), date_longue(v["echeance"]))
            ech.setTextAlignment(0x0001 | 0x0080)  # gauche, centré verticalement
            self.t.setItem(i, 3, ech)
            self.t.setItem(i, 4, ItemNum(v["montant"]))
            self.t.setItem(i, 5, item(etat, couleur=coul, gras=retard))
            self.t.setItem(i, 6, item(v["mode"] or ""))
        self.t.setSortingEnabled(True)
        self._etat()

    def _courant(self):
        vid = id_selection(self.t)
        return self.app.db.versement(vid) if vid else None

    def _etat(self):
        v = self._courant()
        self.b_payer.setEnabled(bool(v) and not v["paye"])
        self.b_annuler.setEnabled(bool(v) and bool(v["paye"]))
        self.b_recu.setEnabled(bool(v) and bool(v["paye"]))
        self.b_rappel.setEnabled(bool(v) and not v["paye"])

    def _payer(self):
        v = self._courant()
        if not v or v["paye"]:
            return
        d = DialoguePaiement(self, v["nom"], v["montant"])
        if d.exec():
            self.app.db.marquer_paye(v["id"], True, d.mode.currentText(), d.quand.date().toPython())
            self.app.rafraichir()
            self.app.toast(f"Paiement de {argent(v['montant'])} enregistré pour {v['nom']}.")

    def _annuler(self):
        v = self._courant()
        if v:
            self.app.db.marquer_paye(v["id"], False)
            self.app.rafraichir()
            self.app.toast("Paiement annulé.")

    def _recu(self):
        v = self._courant()
        if v:
            self.app.pdf_recu(v["id"])

    def _rappel(self):
        from PySide6.QtWidgets import QApplication
        v = self._courant()
        if not v:
            return
        p = self.app.p
        retard = v["echeance"] < date.today().isoformat()
        prenom = v["nom"].split()[0] if v["nom"] else ""
        if v["libelle"]:
            phrase = (f"la visite de déneigement du {date_longue(v['echeance'])} ({argent(v['montant'])}) "
                      "est toujours à payer.")
        elif retard:
            phrase = (f"le versement {v['no']} de votre contrat de déneigement ({argent(v['montant'])}) "
                      f"était dû le {date_longue(v['echeance'])}.")
        else:
            phrase = (f"le versement {v['no']} de votre contrat de déneigement ({argent(v['montant'])}) "
                      f"arrive à échéance le {date_longue(v['echeance'])}.")
        debut = "Petit rappel" if not retard else "Sauf erreur de notre part"
        texte = (f"Bonjour {prenom},\n\n{debut} : {phrase}\n\n"
                 f"Vous pouvez payer par virement Interac{(' à ' + p.courriel) if p.courriel else ''}.\n\n"
                 f"Merci et bon hiver !\n{p.nom_entreprise}" + (f"\n{p.telephone}" if p.telephone else ""))
        QApplication.clipboard().setText(texte)
        self.app.toast("Rappel copié. Collez-le dans un texto ou un courriel.")
