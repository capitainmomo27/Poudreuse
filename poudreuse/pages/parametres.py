"""Page Paramètres : l'entreprise, ses coûts et ses règles de prix."""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit, QCheckBox, QPushButton,
                               QPlainTextEdit, QScrollArea, QFrame, QFileDialog, QMessageBox, QLabel)

from ..calculs import Parametres
from ..widgets import entete_page, Panneau, etiquette, nombre, entier

# (clé, libellé, type, min, max, suffixe, décimales, aide)  — type « % » : stocké en fraction
GROUPES = [
    ("Votre entreprise", [
        ("nom_entreprise", "Nom de l'entreprise", "texte"),
        ("telephone", "Téléphone", "texte"),
        ("adresse", "Adresse", "texte"),
        ("ville", "Ville et code postal", "texte"),
        ("courriel", "Courriel (aussi utilisé pour les virements Interac)", "texte"),
        ("neq", "NEQ", "texte"),
        ("no_tps", "Numéro de TPS", "texte"),
        ("no_tvq", "Numéro de TVQ", "texte"),
    ]),
    ("Coûts d'exploitation", [
        ("taux_horaire_mo", "Salaire horaire, charges incluses", "num", 0, 500, "$/h", 2,
         "Payez-vous vous-même : incluez votre propre salaire même si vous travaillez seul."),
        ("personnes_par_equipe", "Personnes par équipe", "ent", 1, 10, "", 0, ""),
        ("cout_equipement_h", "Coût de l'équipement", "num", 0, 500, "$/h", 2,
         "Amortissement du camion et de la gratte, entretien et assurance, divisés par les heures de la saison."),
        ("prix_carburant_l", "Prix du carburant", "num", 0, 5, "$/L", 3, ""),
        ("conso_l_h", "Consommation en déneigement", "num", 0, 100, "L/h", 1, ""),
        ("conso_l_100km", "Consommation sur la route", "num", 0, 100, "L/100 km", 1, ""),
        ("cout_abrasif_kg", "Prix de l'abrasif", "num", 0, 10, "$/kg", 3, ""),
        ("abrasif_kg_100pi2", "Abrasif épandu", "num", 0, 10, "kg/100 pi²", 2, ""),
        ("frequence_abrasif", "Visites avec épandage", "%", 0, 100, "%", 0, ""),
        ("frais_fixes_saison", "Frais fixes de la saison", "num", 0, 1e6, "$", 2,
         "Assurance responsabilité, immatriculation, publicité, piquets, entretien avant la saison."),
        ("nb_clients_prevus", "Nombre de clients prévus", "ent", 1, 2000, "", 0,
         "Les frais fixes sont répartis entre ces clients."),
    ]),
    ("Route", [
        ("minutes_entre_clients", "Temps de route entre deux clients", "num", 0, 60, "min", 1, ""),
        ("km_entre_clients", "Distance entre deux clients", "num", 0, 50, "km", 1, ""),
        ("km_depot_aller_retour", "Aller-retour au garage", "num", 0, 200, "km", 1, ""),
        ("heures_max_tempete", "Heures maximum par tempête pour une équipe", "num", 1, 24, "h", 1,
         "Au-delà, Poudreuse vous avertit qu'il faut une deuxième équipe."),
    ]),
    ("Règles de prix", [
        ("tempetes_normales", "Tempêtes dans un hiver normal", "ent", 1, 80, "", 0,
         "Environ 20 à 30 dans la région de Montréal, davantage à Québec et au Saguenay."),
        ("facteur_repasse", "Facteur de retour après la charrue", "num", 1, 3, "×", 2,
         "1,25 signifie un retour pour le bourrelet une tempête sur quatre."),
        ("marge_visee", "Marge visée", "%", 0, 80, "%", 0, ""),
        ("prix_minimum", "Prix minimum d'un contrat saisonnier", "num", 0, 10000, "$", 2, ""),
        ("prix_minimum_visite", "Prix minimum d'une visite", "num", 0, 1000, "$", 2, ""),
        ("prime_a_la_visite", "Majoration du service à la visite", "num", 1, 5, "×", 2,
         "Le service sur appel est moins prévisible ; il se vend plus cher."),
        ("seuil_cm", "Accumulation qui déclenche le service", "ent", 1, 30, "cm", 0, ""),
        ("saison", "Saison en cours", "texte"),
    ]),
]


class PageParametres(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.champs: dict[str, tuple[str, QWidget]] = {}
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
        lay.addWidget(entete_page("Paramètres", "Vos coûts réels donnent des prix justes. Prenez dix minutes pour les ajuster."))

        for titre, champs in GROUPES:
            pan = Panneau()
            pan.lay.addWidget(etiquette(titre, "section"))
            g = QGridLayout()
            g.setHorizontalSpacing(18)
            g.setVerticalSpacing(4)
            for i, spec in enumerate(champs):
                cle, lib, typ = spec[:3]
                if typ == "texte":
                    w = QLineEdit()
                elif typ == "ent":
                    w = entier(int(spec[3]), int(spec[4]), 0, spec[5])
                else:
                    w = nombre(spec[3], spec[4], 0, spec[5], spec[6])
                self.champs[cle] = (typ, w)
                r, c = (i // 2) * 4, i % 2
                g.addWidget(etiquette(lib), r, c)
                g.addWidget(w, r + 1, c)
                if len(spec) > 7 and spec[7]:
                    a = etiquette(spec[7], "aide")
                    g.addWidget(a, r + 2, c)
                g.setRowMinimumHeight(r + 3, 10)
                g.setColumnStretch(c, 1)
            pan.lay.addLayout(g)
            if titre == "Votre entreprise":
                self.taxes = QCheckBox("Inscrit aux fichiers de la TPS et de la TVQ (revenus de plus de 30 000 $ par an)")
                pan.lay.addWidget(self.taxes)
                ligne = QHBoxLayout()
                self.logo = QLabel("Aucun logo")
                self.logo.setObjectName("aide")
                b_logo = QPushButton("Choisir un logo")
                b_sans = QPushButton("Retirer")
                ligne.addWidget(b_logo)
                ligne.addWidget(b_sans)
                ligne.addWidget(self.logo, 1)
                pan.lay.addLayout(ligne)
                b_logo.clicked.connect(self._choisir_logo)
                b_sans.clicked.connect(lambda: self._definir_logo(""))
            lay.addWidget(pan)

        pan = Panneau()
        pan.lay.addWidget(etiquette("Conditions du contrat", "section"))
        pan.lay.addWidget(etiquette("Imprimées sur chaque soumission et contrat. {seuil} est remplacé par l'accumulation de déclenchement.", "aide"))
        self.conditions = QPlainTextEdit()
        self.conditions.setMinimumHeight(120)
        pan.lay.addWidget(self.conditions)
        lay.addWidget(pan)

        pan = Panneau()
        pan.lay.addWidget(etiquette("Vos données", "section"))
        self.lib_dossier = etiquette("", "aide")
        pan.lay.addWidget(self.lib_dossier)
        ligne = QHBoxLayout()
        b_sauv = QPushButton("Faire une copie de sauvegarde")
        b_rest = QPushButton("Restaurer une sauvegarde")
        b_doss = QPushButton("Ouvrir le dossier des données")
        b_demo = QPushButton("Essayer avec des clients fictifs")
        b_demo.clicked.connect(self._demo)
        for b in (b_sauv, b_rest, b_doss, b_demo):
            ligne.addWidget(b)
        ligne.addStretch()
        pan.lay.addLayout(ligne)
        lay.addWidget(pan)

        bas = QHBoxLayout()
        self.b_enr = QPushButton("Enregistrer les paramètres")
        self.b_enr.setObjectName("principal")
        self.b_enr.setMinimumHeight(40)
        b_def = QPushButton("Remettre les coûts par défaut")
        bas.addWidget(self.b_enr)
        bas.addWidget(b_def)
        bas.addStretch()
        lay.addLayout(bas)
        lay.addStretch()

        self.b_enr.clicked.connect(self.enregistrer)
        b_def.clicked.connect(self._defaut)
        b_sauv.clicked.connect(self._sauvegarder)
        b_rest.clicked.connect(self._restaurer)
        b_doss.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.app.db.chemin.parent))))
        self._logo = ""

    def rafraichir(self):
        self._afficher(self.app.p)
        self.lib_dossier.setText(f"Tout est enregistré sur cet ordinateur, dans {self.app.db.chemin}. "
                                 "Faites une copie de sauvegarde sur une clé USB ou dans le nuage au moins une fois par mois.")

    def _afficher(self, p: Parametres):
        for cle, (typ, w) in self.champs.items():
            v = getattr(p, cle)
            if typ == "texte":
                w.setText(str(v))
            elif typ == "%":
                w.setValue(v * 100)
            else:
                w.setValue(v)
        self.taxes.setChecked(p.inscrit_taxes)
        self.conditions.setPlainText(p.conditions)
        self._definir_logo(p.logo)

    def _definir_logo(self, chemin: str):
        self._logo = chemin
        self.logo.setText(os.path.basename(chemin) if chemin else "Aucun logo. Il apparaîtra en haut de vos documents.")

    def _choisir_logo(self):
        chemin, _ = QFileDialog.getOpenFileName(self, "Choisir un logo", "", "Images (*.png *.jpg *.jpeg)")
        if chemin:
            # copie dans le dossier des données : le logo reste disponible même si l'original est déplacé
            import shutil
            from pathlib import Path
            dest = self.app.db.chemin.parent / f"logo{Path(chemin).suffix.lower()}"
            try:
                shutil.copyfile(chemin, dest)
                chemin = str(dest)
            except OSError:
                pass
            self._definir_logo(chemin)

    def lire(self) -> Parametres:
        valeurs = {}
        for cle, (typ, w) in self.champs.items():
            if typ == "texte":
                valeurs[cle] = w.text().strip()
            elif typ == "%":
                valeurs[cle] = w.value() / 100
            else:
                valeurs[cle] = w.value()
        valeurs["inscrit_taxes"] = self.taxes.isChecked()
        valeurs["conditions"] = self.conditions.toPlainText().strip()
        valeurs["logo"] = self._logo
        return replace(self.app.p, **valeurs)

    def enregistrer(self):
        p = self.lire()
        if not p.nom_entreprise:
            QMessageBox.warning(self, "Nom manquant", "Entrez le nom de votre entreprise : il apparaît sur vos documents.")
            return
        self.app.db.enregistrer_parametres(p)
        self.app.p = p
        self.app.changer_saison(p.saison)
        self.app.toast("Paramètres enregistrés. Les prix sont recalculés.")

    def _defaut(self):
        d = Parametres()
        actuel = self.lire()
        garder = {k: getattr(actuel, k) for k in ("nom_entreprise", "adresse", "ville", "telephone", "courriel",
                                                   "neq", "no_tps", "no_tvq", "logo", "inscrit_taxes", "saison")}
        self._afficher(replace(d, **garder))
        self.app.toast("Coûts par défaut affichés. Enregistrez pour les appliquer.")

    def _demo(self):
        if self.app.db.contrats():
            QMessageBox.information(self, "Données existantes",
                                    "Les clients fictifs ne peuvent être ajoutés que dans un logiciel vide, "
                                    "pour ne pas se mélanger à vos vrais clients.")
            return
        if QMessageBox.question(self, "Clients fictifs",
                                "Ajouter 22 clients fictifs, des paiements et des tempêtes pour découvrir le logiciel ?\n\n"
                                "Faites une copie de sauvegarde avant de saisir vos vrais clients : vous pourrez "
                                "repartir à zéro en supprimant le fichier des données.") != QMessageBox.StandardButton.Yes:
            return
        from ..demo import remplir
        remplir(self.app.db, garder_entreprise=True)
        self.app.p = self.app.db.parametres()
        self.app.changer_saison(self.app.p.saison)
        self.app.aller("tableau")
        self.app.toast("Clients fictifs ajoutés.")

    def _sauvegarder(self):
        from datetime import date
        chemin, _ = QFileDialog.getSaveFileName(self, "Copie de sauvegarde",
                                                str(self.app.dossier_documents() / f"poudreuse-sauvegarde-{date.today()}.db"),
                                                "Sauvegarde Poudreuse (*.db)")
        if chemin:
            self.app.db.sauvegarder_vers(chemin)
            self.app.toast("Copie de sauvegarde créée.")

    def _restaurer(self):
        chemin, _ = QFileDialog.getOpenFileName(self, "Restaurer une sauvegarde", str(self.app.dossier_documents()),
                                                "Sauvegarde Poudreuse (*.db)")
        if not chemin:
            return
        if QMessageBox.question(self, "Restaurer",
                                "Vos données actuelles seront remplacées par celles de la sauvegarde. Continuer ?") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.app.db.restaurer_depuis(chemin)
        except Exception as e:
            QMessageBox.critical(self, "Restauration impossible", f"Ce fichier n'est pas une sauvegarde Poudreuse valide.\n\n{e}")
            return
        self.app.p = self.app.db.parametres()
        self.app.changer_saison(self.app.p.saison)
        self.app.toast("Sauvegarde restaurée.")
