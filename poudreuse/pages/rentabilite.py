"""Page Rentabilité : la saison complète, tempête par tempête."""
from __future__ import annotations

import json
import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QScrollArea, QFrame

from PySide6.QtGui import QColor

from ..calculs import Entree, TYPES_CONTRAT, rentabilite_saison, minutes_par_visite, visites_saison, argent
from ..theme import BALISE
from ..widgets import (entete_page, Panneau, BandeKpi, CourbeProfit, tableau, item, ItemNum, id_selection,
                       etiquette, nombre)


class PageRentabilite(QWidget):
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
        lay.addWidget(entete_page("Rentabilité de la saison",
                                  "Calculée sur les contrats signés. Bougez les curseurs pour tester un autre hiver."))

        self.bande = BandeKpi(["Revenus de la saison", "Coût d'une tempête", "Heures par tempête",
                               "Profit, hiver normal"])
        lay.addWidget(self.bande)

        # Simulateur
        sim = Panneau()
        ligne = QHBoxLayout()
        ligne.setSpacing(18)
        col1 = QVBoxLayout()
        self.lib_tempetes = etiquette("", "etiquette")
        self.curseur = QSlider(Qt.Orientation.Horizontal)
        self.curseur.setRange(5, 45)
        col1.addWidget(self.lib_tempetes)
        col1.addWidget(self.curseur)
        col2 = QVBoxLayout()
        col2.addWidget(etiquette("Prix du carburant pour la simulation", "etiquette"))
        self.carbu = nombre(0.5, 5, 1.65, "$/L", 2, 0.05)
        col2.addWidget(self.carbu)
        ligne.addLayout(col1, 3)
        ligne.addLayout(col2, 1)
        sim.lay.addLayout(ligne)
        self.verdict = etiquette("", "section")
        sim.lay.addWidget(self.verdict)
        self.courbe = CourbeProfit()
        sim.lay.addWidget(self.courbe)
        lay.addWidget(sim)

        # Route
        lay.addWidget(etiquette("Ordre de la route", "section"))
        lay.addWidget(etiquette("Le taux horaire réel montre ce que chaque client vous rapporte par heure de travail. "
                                "Les clients en orange sont sous votre coût horaire.", "aide"))
        self.t = tableau(["Client", "Adresse", "Min. par visite", "Visites", "Prix", "Taux horaire réel"], etirer=1)
        lay.addWidget(self.t)
        boutons = QHBoxLayout()
        self.b_haut = QPushButton("Monter dans la route")
        self.b_bas = QPushButton("Descendre dans la route")
        boutons.addWidget(self.b_haut)
        boutons.addWidget(self.b_bas)
        boutons.addStretch()
        lay.addLayout(boutons)

        self.curseur.valueChanged.connect(self._simuler)
        self.carbu.valueChanged.connect(self._simuler)
        self.b_haut.clicked.connect(lambda: self._deplacer(-1))
        self.b_bas.clicked.connect(lambda: self._deplacer(1))

    def rafraichir(self):
        p = self.app.p
        self.curseur.blockSignals(True)
        self.carbu.blockSignals(True)
        self.curseur.setValue(p.tempetes_normales)
        self.carbu.setValue(p.prix_carburant_l)
        self.curseur.blockSignals(False)
        self.carbu.blockSignals(False)
        self._contrats = []
        for r in self.app.db.contrats(self.app.saison, "Signé"):
            self._contrats.append({"id": r["id"], "nom": r["nom"],
                                   "adresse": ", ".join(x for x in (r["adresse"], r["ville"]) if x),
                                   "entree": Entree.from_dict(json.loads(r["entree_json"])), "prix": r["prix"]})
        self._simuler()
        self._route()

    def _params_sim(self):
        from dataclasses import replace
        return replace(self.app.p, prix_carburant_l=self.carbu.value())

    def _simuler(self, *_):
        p = self._params_sim()
        t = self.curseur.value()
        self.lib_tempetes.setText(f"Nombre de tempêtes dans la saison : {t}  (votre moyenne : {self.app.p.tempetes_normales})")
        r = rentabilite_saison(self._contrats, p, tempetes_max=45)
        k = self.bande.kpis
        k[0].definir(argent(r.revenus), detail=f"Revenus de la saison ({r.nb_contrats} contrats signés)")
        k[1].definir(argent(r.cout_tempete), detail=f"Coût d'une tempête ({r.km_tempete:.0f} km)")
        heures = f"{r.heures_tempete:.1f} h".replace(".", ",")
        alerte = r.equipes_requises > 1
        k[2].definir(heures, alerte=alerte,
                     detail=(f"Heures par tempête : {r.equipes_requises} équipes nécessaires" if alerte
                             else "Heures par tempête, une équipe"))
        k[3].definir(argent(r.profit_normal), alerte=r.profit_normal < 0)

        if not self._contrats:
            self.verdict.setText("Aucun contrat signé pour cette saison.")
            self.courbe.definir([], [])
            return
        profit_t = dict(r.courbe)[t]
        if math.isinf(r.seuil_tempetes):
            seuil = "Vous restez rentable même avec 45 tempêtes."
        elif r.seuil_tempetes == 0:
            seuil = "Vos revenus ne couvrent pas vos frais fixes de la saison."
        else:
            seuil = f"Vous perdez de l'argent à partir de {r.seuil_tempetes} tempêtes."
        self.verdict.setText(f"Avec {t} tempêtes : {argent(profit_t)} de profit. {seuil}")
        n = self.app.p.tempetes_normales
        self.courbe.definir(r.courbe, [("Léger", round(n * 0.75)), ("Normal", n), ("Neigeux", round(n * 1.4))], t)

    def _route(self):
        p = self.app.p
        cout_h = p.taux_horaire_mo * max(p.personnes_par_equipe, 1) + p.cout_equipement_h
        self.t.setRowCount(len(self._contrats))
        self.t.setFixedHeight(self.t.horizontalHeader().sizeHint().height() + 38 * max(len(self._contrats), 3) + 4)
        for i, c in enumerate(self._contrats):
            e = c["entree"]
            m = minutes_par_visite(e, p) + p.minutes_entre_clients
            v = visites_saison(e, p)
            if e.type_contrat == TYPES_CONTRAT[2]:
                taux = c["prix"] / (m / 60) if m else 0
            else:
                taux = c["prix"] / (m * v / 60) if m and v else 0
            faible = taux < cout_h
            self.t.setItem(i, 0, item(c["nom"], c["id"], gras=True))
            self.t.setItem(i, 1, item(c["adresse"]))
            self.t.setItem(i, 2, ItemNum(m, f"{m:.1f}".replace(".", ",")))
            self.t.setItem(i, 3, ItemNum(v, f"{v:.0f}"))
            self.t.setItem(i, 4, ItemNum(c["prix"]))
            it = ItemNum(taux, f"{argent(taux)}/h")
            if faible:
                it.setForeground(QColor(BALISE))
            self.t.setItem(i, 5, it)

    def _deplacer(self, d):
        cid = id_selection(self.t)
        if not cid:
            return
        self.app.db.deplacer_route(cid, d, self.app.saison)
        self.rafraichir()
        for i in range(self.t.rowCount()):
            if self.t.item(i, 0).data(Qt.ItemDataRole.UserRole) == cid:
                self.t.selectRow(i)
                break
