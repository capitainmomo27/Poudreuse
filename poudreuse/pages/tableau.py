"""Page d'accueil : l'état de la saison en un coup d'œil."""
from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea, QFrame, QLabel

from ..calculs import argent
from ..pdf import date_longue
from ..theme import BALISE
from ..widgets import entete_page, BandeKpi, Panneau, tableau, item, ItemNum, etiquette


class PageTableau(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        ext = QVBoxLayout(self)
        ext.setContentsMargins(0, 0, 0, 0)
        defile = QScrollArea()
        defile.setWidgetResizable(True)
        defile.setFrameShape(QFrame.Shape.NoFrame)
        contenu = QWidget()
        contenu.setObjectName("fond")
        defile.setWidget(contenu)
        ext.addWidget(defile)

        lay = QVBoxLayout(contenu)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)
        self.entete = entete_page("Tableau de bord", " ")
        self.sous_titre = self.entete.findChild(QLabel, "sousTitre")
        lay.addWidget(self.entete)

        # Premier démarrage
        self.accueil = Panneau()
        self.accueil.lay.addWidget(etiquette("Bienvenue dans Poudreuse", "section"))
        self.accueil.lay.addWidget(etiquette(
            "Commencez par entrer le nom de votre entreprise et vos coûts (taux horaire, carburant, frais fixes). "
            "Les prix suggérés en dépendent directement.", "aide"))
        b = QHBoxLayout()
        self.b_param = QPushButton("Configurer mon entreprise")
        self.b_param.setObjectName("principal")
        b.addWidget(self.b_param)
        b.addStretch()
        self.accueil.lay.addLayout(b)
        lay.addWidget(self.accueil)

        self.bande1 = BandeKpi(["Contrats signés", "Encaissé", "À recevoir", "En retard"])
        lay.addWidget(self.bande1)
        self.bande2 = BandeKpi(["Soumissions en attente", "Tempêtes", "Dépenses", "Profit réel à ce jour"])
        lay.addWidget(self.bande2)

        colonnes = QHBoxLayout()
        colonnes.setSpacing(14)
        g = QVBoxLayout()
        g.addWidget(etiquette("Paiements en retard", "section"))
        self.t_retard = tableau(["Client", "Échéance", "Montant"], etirer=0)
        self.t_retard.setMinimumHeight(240)
        g.addWidget(self.t_retard)
        self.vide_retard = etiquette("Aucun paiement en retard.", "aide")
        g.addWidget(self.vide_retard)
        d = QVBoxLayout()
        d.addWidget(etiquette("Soumissions à relancer", "section"))
        self.t_soum = tableau(["Client", "Envoyée le", "Prix"], etirer=0)
        self.t_soum.setMinimumHeight(240)
        d.addWidget(self.t_soum)
        self.vide_soum = etiquette("Aucune soumission en attente.", "aide")
        d.addWidget(self.vide_soum)
        colonnes.addLayout(g, 1)
        colonnes.addLayout(d, 1)
        lay.addLayout(colonnes)

        actions = QHBoxLayout()
        self.b_nouvelle = QPushButton("Nouvelle soumission")
        self.b_nouvelle.setObjectName("principal")
        actions.addWidget(self.b_nouvelle)
        actions.addStretch()
        lay.addLayout(actions)
        lay.addStretch()

        self.b_param.clicked.connect(lambda: self.app.aller("parametres"))
        self.b_nouvelle.clicked.connect(self.app.nouvelle_soumission)
        self.t_soum.cellDoubleClicked.connect(self._ouvrir_soum)
        self.t_retard.cellDoubleClicked.connect(lambda *_: self.app.aller("paiements"))

    def rafraichir(self):
        db, p, s = self.app.db, self.app.p, self.app.saison
        self.sous_titre.setText(f"Saison {s}, {p.nom_entreprise}")
        self.accueil.setVisible(p.nom_entreprise == "Mon entreprise de déneigement")
        res = db.resume(s)
        k = self.bande1.kpis
        k[0].definir(f"{res['nb_signes']}", detail=f"Contrats signés, {argent(res['revenus'])} avant taxes")
        k[1].definir(argent(res["encaisse"]))
        k[2].definir(argent(res["a_recevoir"]))
        k[3].definir(argent(res["montant_retard"]), alerte=res["montant_retard"] > 0,
                     detail=f"En retard ({res['nb_retard']} versement{'s' * (res['nb_retard'] > 1)})")

        k = self.bande2.kpis
        k[0].definir(f"{res['nb_soumissions']}", detail=f"Soumissions en attente, {argent(res['valeur_soumissions'])}")
        k[1].definir(f"{res['nb_tempetes']} sur {p.tempetes_normales}", detail="Tempêtes notées dans le journal")
        k[2].definir(argent(res["depenses"]))
        reel = res["encaisse"] / (1.14975 if p.inscrit_taxes else 1) - res["depenses"]
        k[3].definir(argent(reel), alerte=reel < 0, detail="Profit réel à ce jour (encaissé avant taxes, moins dépenses)")

        aujourdhui = date.today().isoformat()
        retards = [v for v in db.versements(s) if not v["paye"] and v["echeance"] < aujourdhui]
        self.t_retard.setRowCount(len(retards))
        for i, v in enumerate(retards):
            self.t_retard.setItem(i, 0, item(v["nom"], v["id"], gras=True))
            self.t_retard.setItem(i, 1, item(date_longue(v["echeance"]), couleur=BALISE))
            self.t_retard.setItem(i, 2, ItemNum(v["montant"]))
        self.t_retard.setVisible(bool(retards))
        self.vide_retard.setVisible(not retards)

        soum = db.contrats(s, "Soumission")
        self.t_soum.setRowCount(len(soum))
        for i, r in enumerate(soum):
            self.t_soum.setItem(i, 0, item(r["nom"], r["id"], gras=True))
            self.t_soum.setItem(i, 1, item(date_longue(r["cree_le"])))
            self.t_soum.setItem(i, 2, ItemNum(r["prix"]))
        self.t_soum.setVisible(bool(soum))
        self.vide_soum.setVisible(not soum)

    def _ouvrir_soum(self, ligne, _col):
        from PySide6.QtCore import Qt
        cid = self.t_soum.item(ligne, 0).data(Qt.ItemDataRole.UserRole)
        self.app.ouvrir_contrat(cid)
