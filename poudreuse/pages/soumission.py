"""Page Soumission : on chiffre une entrée en direct et on l'enregistre."""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLineEdit, QComboBox, QCheckBox,
                               QPushButton, QScrollArea, QFrame, QLabel, QPlainTextEdit, QMessageBox)

from ..calculs import Entree, METHODES, TYPES_CONTRAT, calculer, taxes, argent
from ..widgets import Panneau, entete_page, etiquette, nombre, entier, separateur


class PageSoumission(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.contrat_id: int | None = None
        self.client_id: int | None = None
        self._resultat = None
        self._chargement = False

        racine = QHBoxLayout(self)
        racine.setContentsMargins(0, 0, 0, 0)
        racine.setSpacing(0)

        # ---------------- colonne de gauche : formulaire défilant ----------------
        defile = QScrollArea()
        defile.setWidgetResizable(True)
        defile.setFrameShape(QFrame.Shape.NoFrame)
        contenu = QWidget()
        contenu.setObjectName("fond")
        col = QVBoxLayout(contenu)
        col.setContentsMargins(32, 28, 24, 28)
        col.setSpacing(14)
        defile.setWidget(contenu)

        self.entete = entete_page("Nouvelle soumission", "Le prix se calcule pendant que vous remplissez les champs.")
        col.addWidget(self.entete)
        self.bandeau_modif = etiquette("", "aide")
        self.bandeau_modif.hide()
        col.addWidget(self.bandeau_modif)

        # Client
        pc = Panneau()
        pc.lay.addWidget(etiquette("Client", "section"))
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(6)
        self.nom = QLineEdit(placeholderText="Nom du client")
        self.telephone = QLineEdit(placeholderText="514-555-0123")
        self.courriel = QLineEdit(placeholderText="client@exemple.com")
        self.adresse = QLineEdit(placeholderText="123, rue des Érables")
        self.ville = QLineEdit(placeholderText="Ville")
        self.notes = QPlainTextEdit(placeholderText="Notes : borne-fontaine, voiture dans la rue, chien…")
        self.notes.setFixedHeight(64)
        self._grille(g, 0, "Nom", self.nom, "Téléphone", self.telephone)
        self._grille(g, 2, "Adresse", self.adresse, "Ville", self.ville)
        self._grille(g, 4, "Courriel", self.courriel)
        g.addWidget(etiquette("Notes"), 6, 0, 1, 2)
        g.addWidget(self.notes, 7, 0, 1, 2)
        pc.lay.addLayout(g)
        col.addWidget(pc)

        # Entrée
        pe = Panneau()
        titre_surface = QHBoxLayout()
        titre_surface.addWidget(etiquette("Surface à déneiger", "section"))
        titre_surface.addStretch()
        self.surface = etiquette("", "aide")
        self.surface.setWordWrap(False)
        titre_surface.addWidget(self.surface)
        pe.lay.addLayout(titre_surface)
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(6)
        self.longueur = nombre(0, 1000, 40, "pi", 0)
        self.largeur = nombre(0, 400, 20, "pi", 0)
        self.methode = QComboBox()
        self.methode.addItems(list(METHODES))
        self.methode.setCurrentText("Pick-up avec gratte")
        self.trottoir = nombre(0, 1000, 0, "pi", 0)
        self.perrons = entier(0, 20, 0)
        self._grille(g, 0, "Longueur de l'entrée", self.longueur, "Largeur", self.largeur)
        self._grille(g, 2, "Méthode", self.methode, "Trottoir ou allée (pieds linéaires)", self.trottoir)
        self._grille(g, 4, "Perrons, marches ou balcons", self.perrons)
        pe.lay.addLayout(g)
        self.abrasif = QCheckBox("Épandage d'abrasif au besoin")
        self.repasse = QCheckBox("Retour après le passage de la charrue municipale")
        self.repasse.setChecked(True)
        pe.lay.addWidget(self.abrasif)
        pe.lay.addWidget(self.repasse)
        col.addWidget(pe)

        # Contrat
        pk = Panneau()
        pk.lay.addWidget(etiquette("Contrat", "section"))
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(6)
        self.type_contrat = QComboBox()
        self.type_contrat.addItems(TYPES_CONTRAT)
        self.visites = entier(1, 200, 20, "visites")
        self.versements = QComboBox()
        self.versements.addItems(["1 versement", "2 versements", "3 versements", "4 versements"])
        self.versements.setCurrentIndex(1)
        self.frais = nombre(0, 100000, 0, "$")
        self.rabais = nombre(0, 50, 0, "%", 1)
        self._grille(g, 0, "Type de contrat", self.type_contrat, "Visites incluses", self.visites)
        self._grille(g, 2, "Paiement", self.versements, "Frais additionnels (piquets, installation…)", self.frais)
        self._grille(g, 4, "Rabais", self.rabais)
        pk.lay.addLayout(g)
        pk.lay.addWidget(separateur())
        self.prix_manuel = QCheckBox("Choisir moi-même le prix")
        self.prix_demande = nombre(0, 100000, 0, "$")
        self.prix_demande.setEnabled(False)
        ligne = QHBoxLayout()
        ligne.addWidget(self.prix_manuel)
        ligne.addStretch()
        ligne.addWidget(self.prix_demande)
        self.prix_demande.setFixedWidth(160)
        pk.lay.addLayout(ligne)
        col.addWidget(pk)
        col.addStretch()

        racine.addWidget(defile, 1)

        # ---------------- colonne de droite : le panneau de prix ----------------
        droite = QWidget()
        droite.setObjectName("fond")
        droite.setFixedWidth(380)
        dl = QVBoxLayout(droite)
        dl.setContentsMargins(8, 28, 32, 28)
        dl.setSpacing(12)

        signe = QFrame()
        signe.setObjectName("panneauSigne")
        sl = QVBoxLayout(signe)
        sl.setContentsMargins(24, 22, 24, 22)
        sl.setSpacing(4)
        self.lib_prix = etiquette("Prix de la saison, avant taxes", "signeTitre")
        sl.addWidget(self.lib_prix)
        self.prix = QLabel("0 $")
        self.prix.setObjectName("prixGeant")
        sl.addWidget(self.prix)
        self.ligne_total = etiquette("")
        sl.addWidget(self.ligne_total)
        sl.addSpacing(10)
        ls = QFrame()
        ls.setObjectName("ligneSigne")
        sl.addWidget(ls)
        sl.addSpacing(8)
        self.details = QGridLayout()
        self.details.setVerticalSpacing(5)
        sl.addLayout(self.details)
        sl.addSpacing(8)
        ls2 = QFrame()
        ls2.setObjectName("ligneSigne")
        sl.addWidget(ls2)
        sl.addSpacing(6)
        sl.addWidget(etiquette("Profit selon l'hiver", "signeTitre"))
        self.scen = QGridLayout()
        self.scen.setVerticalSpacing(5)
        sl.addLayout(self.scen)
        self.alertes = etiquette("", "signeAlerte")
        sl.addWidget(self.alertes)
        dl.addWidget(signe)

        self.btn_enregistrer = QPushButton("Enregistrer la soumission")
        self.btn_enregistrer.setObjectName("principal")
        self.btn_pdf = QPushButton("Enregistrer et créer le PDF")
        self.btn_nouveau = QPushButton("Nouvelle soumission")
        for b in (self.btn_enregistrer, self.btn_pdf, self.btn_nouveau):
            b.setMinimumHeight(40)
            dl.addWidget(b)
        dl.addStretch()
        racine.addWidget(droite)

        # ---------------- connexions ----------------
        for w in (self.longueur, self.largeur, self.trottoir, self.frais, self.rabais, self.prix_demande):
            w.valueChanged.connect(self.recalculer)
        for w in (self.perrons, self.visites):
            w.valueChanged.connect(self.recalculer)
        for w in (self.methode, self.type_contrat, self.versements):
            w.currentIndexChanged.connect(self.recalculer)
        for w in (self.abrasif, self.repasse):
            w.toggled.connect(self.recalculer)
        self.prix_manuel.toggled.connect(self._bascule_prix)
        self.btn_enregistrer.clicked.connect(lambda: self.enregistrer(pdf=False))
        self.btn_pdf.clicked.connect(lambda: self.enregistrer(pdf=True))
        self.btn_nouveau.clicked.connect(self.reinitialiser)
        self.recalculer()

    # ------------------------------------------------------------------ outils
    @staticmethod
    def _grille(g: QGridLayout, ligne: int, l1: str, w1, l2: str | None = None, w2=None):
        g.addWidget(etiquette(l1), ligne, 0)
        g.addWidget(w1, ligne + 1, 0)
        if l2:
            g.addWidget(etiquette(l2), ligne, 1)
            g.addWidget(w2, ligne + 1, 1)
        g.setColumnStretch(0, 1)
        g.setColumnStretch(1, 1)

    def _bascule_prix(self, actif: bool):
        self.prix_demande.setEnabled(actif)
        if actif and self._resultat and not self.prix_demande.value():
            self.prix_demande.setValue(self._resultat.prix)
        self.recalculer()

    def entree(self) -> Entree:
        return Entree(
            longueur_pi=self.longueur.value(), largeur_pi=self.largeur.value(),
            methode=self.methode.currentText(), trottoir_pi=self.trottoir.value(),
            perrons=self.perrons.value(), abrasif=self.abrasif.isChecked(), repasse=self.repasse.isChecked(),
            type_contrat=self.type_contrat.currentText(), visites_incluses=self.visites.value(),
            frais_additionnels=self.frais.value(), rabais_pct=self.rabais.value(),
            nb_versements=self.versements.currentIndex() + 1,
        )

    def _vider(self, grille: QGridLayout):
        while grille.count():
            w = grille.takeAt(0).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def _ligne(self, grille, r, a, b, couleur=None):
        la = QLabel(a)
        lb = QLabel(b)
        lb.setObjectName("signeValeur")
        lb.setAlignment(Qt.AlignmentFlag.AlignRight)
        if couleur:
            lb.setStyleSheet(f"color: {couleur};")
        grille.addWidget(la, r, 0)
        grille.addWidget(lb, r, 1)

    # ------------------------------------------------------------------ calcul
    def recalculer(self, *_):
        if self._chargement:
            return
        p = self.app.p
        e = self.entree()
        self.visites.setEnabled(e.type_contrat == TYPES_CONTRAT[1])
        self.versements.setEnabled(e.type_contrat != TYPES_CONTRAT[2])
        r = calculer(e, p)

        if self.prix_manuel.isChecked() and self.prix_demande.value() > 0:
            ecart = self.prix_demande.value() - r.prix
            r.prix = self.prix_demande.value()
            r.tps, r.tvq, r.total = taxes(r.prix, p.inscrit_taxes)
            r.profit = r.prix - r.cout_total
            r.marge_reelle = r.profit / r.prix if r.prix else 0
            r.scenarios = [(n, t, v + ecart) for n, t, v in r.scenarios]
            r.avertissements = [a for a in r.avertissements if "minimum" not in a]
            if r.marge_reelle < 0.10:
                if not any("10 %" in a for a in r.avertissements):
                    r.avertissements.append("Marge sous 10 % : ce contrat rapporte très peu.")
            else:
                r.avertissements = [a for a in r.avertissements if "10 %" not in a]
        self._resultat = r

        a_la_visite = e.type_contrat == TYPES_CONTRAT[2]
        self.lib_prix.setText("Prix par visite, avant taxes" if a_la_visite else "Prix de la saison, avant taxes")
        self.prix.setText(argent(r.prix).replace(",00 $", " $"))
        if p.inscrit_taxes:
            self.ligne_total.setText(f"{argent(r.total)} avec TPS et TVQ")
        else:
            self.ligne_total.setText("Sans taxes (petit fournisseur)")
        self.surface.setText(f"{r.surface_pi2:,.0f} pi² ({r.surface_m2:,.1f} m²)".replace(",", " ").replace(".", ","))

        self._vider(self.details)
        lignes = [("Temps par visite", f"{r.minutes_visite:.1f} min".replace(".", ","))]
        if not a_la_visite:
            lignes += [("Visites prévues", f"{r.visites_prevues:.0f}"),
                       ("Coût de la saison", argent(r.cout_total))]
            if e.type_contrat != TYPES_CONTRAT[2]:
                lignes.append(("Équivalent par visite", argent(r.prix / max(r.visites_prevues, 1))))
        else:
            lignes.append(("Coût d'une visite", argent(r.cout_total)))
        lignes += [("Profit estimé", argent(r.profit)), ("Marge", f"{r.marge_reelle * 100:.0f} %")]
        for i, (a, b) in enumerate(lignes):
            self._ligne(self.details, i, a, b)

        self._vider(self.scen)
        if r.scenarios:
            for i, (nom, t, v) in enumerate(r.scenarios):
                self._ligne(self.scen, i, f"{nom} ({t} tempêtes)", argent(v), "#FFB27A" if v < 0 else None)
        else:
            self._ligne(self.scen, 0, "Payé à chaque visite", "toujours rentable")
        self.alertes.setText("\n".join(r.avertissements))
        self.alertes.setVisible(bool(r.avertissements))

    # ------------------------------------------------------------------ chargement
    def reinitialiser(self):
        self._chargement = True
        self.contrat_id = self.client_id = None
        for w in (self.nom, self.telephone, self.courriel, self.adresse, self.ville):
            w.clear()
        self.notes.clear()
        d = Entree()
        self._appliquer_entree(d)
        self.prix_manuel.setChecked(False)
        self.prix_demande.setValue(0)
        self.entete.findChild(QLabel, "titrePage").setText("Nouvelle soumission")
        self.bandeau_modif.hide()
        self.btn_enregistrer.setText("Enregistrer la soumission")
        self._chargement = False
        self.recalculer()
        self.nom.setFocus()

    def _appliquer_entree(self, e: Entree):
        self.longueur.setValue(e.longueur_pi)
        self.largeur.setValue(e.largeur_pi)
        self.methode.setCurrentText(e.methode)
        self.trottoir.setValue(e.trottoir_pi)
        self.perrons.setValue(e.perrons)
        self.abrasif.setChecked(e.abrasif)
        self.repasse.setChecked(e.repasse)
        self.type_contrat.setCurrentText(e.type_contrat)
        self.visites.setValue(e.visites_incluses)
        self.versements.setCurrentIndex(max(0, min(e.nb_versements, 4) - 1))
        self.frais.setValue(e.frais_additionnels)
        self.rabais.setValue(e.rabais_pct)

    def charger(self, contrat_id: int):
        c = self.app.db.contrat(contrat_id)
        if not c:
            return
        self._chargement = True
        self.contrat_id, self.client_id = c["id"], c["client_id"]
        self.nom.setText(c["nom"])
        self.telephone.setText(c["telephone"])
        self.courriel.setText(c["courriel"])
        self.adresse.setText(c["adresse"])
        self.ville.setText(c["ville"])
        self.notes.setPlainText(c["notes"])
        e = Entree.from_dict(json.loads(c["entree_json"]))
        self._appliquer_entree(e)
        self._chargement = False
        self.recalculer()
        # le prix enregistré diffère du prix suggéré ? on le garde
        if self._resultat and abs(self._resultat.prix - c["prix"]) > 0.005:
            self.prix_manuel.setChecked(True)
            self.prix_demande.setValue(c["prix"])
        else:
            self.prix_manuel.setChecked(False)
        self.entete.findChild(QLabel, "titrePage").setText(f"Contrat de {c['nom']}")
        self.bandeau_modif.setText(f"Statut : {c['statut']}. Les versements déjà payés sont conservés si vous changez le prix.")
        self.bandeau_modif.show()
        self.btn_enregistrer.setText("Enregistrer les modifications")
        self.recalculer()

    # ------------------------------------------------------------------ enregistrement
    def enregistrer(self, pdf: bool):
        nom = self.nom.text().strip()
        if not nom:
            QMessageBox.warning(self, "Nom manquant", "Entrez le nom du client pour enregistrer la soumission.")
            self.nom.setFocus()
            return
        db, p = self.app.db, self.app.p
        champs = dict(nom=nom, telephone=self.telephone.text().strip(), courriel=self.courriel.text().strip(),
                      adresse=self.adresse.text().strip(), ville=self.ville.text().strip(),
                      notes=self.notes.toPlainText().strip())
        if self.client_id:
            db.modifier_client(self.client_id, **champs)
        else:
            self.client_id = db.ajouter_client(**champs)
        r = self._resultat
        saison = self.app.saison
        if self.contrat_id:
            existant = db.contrat(self.contrat_id)
            saison = existant["saison"] if existant else saison
        nouveau = self.contrat_id is None
        self.contrat_id = db.enregistrer_contrat(self.client_id, saison, self.entree(), r.minutes_visite,
                                                 r.prix, p.inscrit_taxes, self.contrat_id)
        self.app.rafraichir()
        self.app.toast("Soumission enregistrée." if nouveau else "Modifications enregistrées.")
        self.charger(self.contrat_id)
        if pdf:
            self.app.pdf_contrat(self.contrat_id)
