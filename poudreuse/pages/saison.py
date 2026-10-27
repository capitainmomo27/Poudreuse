"""Page Saison : journal des tempêtes et des dépenses."""
from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QDateEdit, QLineEdit, QComboBox,
                               QPushButton, QMessageBox)

from ..calculs import argent
from ..donnees import CATEGORIES_DEPENSES
from ..pdf import date_longue
from ..widgets import entete_page, tableau, item, ItemNum, id_selection, etiquette, nombre, BandeKpi, Panneau


def _date():
    d = QDateEdit(QDate.currentDate())
    d.setCalendarPopup(True)
    d.setDisplayFormat("d MMM yyyy")
    return d


def _champ(titre, w):
    box = QVBoxLayout()
    box.setSpacing(4)
    box.addWidget(etiquette(titre))
    box.addWidget(w)
    return box


class PageSaison(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)
        lay.addWidget(entete_page("Journal de la saison",
                                  "Notez chaque tempête et chaque dépense pour connaître votre vrai profit. "
                                  "Chaque tempête facture automatiquement vos clients à la visite."))
        self.bande = BandeKpi(["Tempêtes", "Neige tombée", "Heures travaillées", "Dépenses"])
        lay.addWidget(self.bande)

        onglets = QTabWidget()
        lay.addWidget(onglets, 1)

        # ---- Tempêtes
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 12, 0, 0)
        form = Panneau(marges=14, horizontal=True)
        self.t_date = _date()
        self.t_cm = nombre(0, 200, 10, "cm", 0)
        self.t_h = nombre(0, 48, 6, "h", 1, 0.5)
        self.t_notes = QLineEdit(placeholderText="Verglas, bris, plaintes…")
        self.t_ajout = QPushButton("Ajouter la tempête")
        self.t_ajout.setObjectName("principal")
        form.lay.addLayout(_champ("Date", self.t_date))
        form.lay.addLayout(_champ("Accumulation", self.t_cm))
        form.lay.addLayout(_champ("Heures de travail", self.t_h))
        form.lay.addLayout(_champ("Notes", self.t_notes), 1)
        bx = QVBoxLayout()
        bx.addStretch()
        bx.addWidget(self.t_ajout)
        form.lay.addLayout(bx)
        l.addWidget(form)
        self.tt = tableau(["Date", "Accumulation", "Heures", "Notes"], etirer=3)
        l.addWidget(self.tt, 1)
        b = QHBoxLayout()
        self.t_suppr = QPushButton("Supprimer la tempête")
        self.t_suppr.setObjectName("danger")
        b.addStretch()
        b.addWidget(self.t_suppr)
        l.addLayout(b)
        onglets.addTab(w, "Tempêtes")

        # ---- Dépenses
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 12, 0, 0)
        form = Panneau(marges=14, horizontal=True)
        self.d_date = _date()
        self.d_cat = QComboBox()
        self.d_cat.addItems(CATEGORIES_DEPENSES)
        self.d_desc = QLineEdit(placeholderText="Plein du pick-up, lame de gratte…")
        self.d_mnt = nombre(0, 1e6, 0, "$")
        self.d_ajout = QPushButton("Ajouter la dépense")
        self.d_ajout.setObjectName("principal")
        form.lay.addLayout(_champ("Date", self.d_date))
        form.lay.addLayout(_champ("Catégorie", self.d_cat))
        form.lay.addLayout(_champ("Description", self.d_desc), 1)
        form.lay.addLayout(_champ("Montant", self.d_mnt))
        bx = QVBoxLayout()
        bx.addStretch()
        bx.addWidget(self.d_ajout)
        form.lay.addLayout(bx)
        l.addWidget(form)
        self.td = tableau(["Date", "Catégorie", "Description", "Montant"], etirer=2)
        l.addWidget(self.td, 1)
        b = QHBoxLayout()
        self.par_cat = etiquette("", "aide")
        b.addWidget(self.par_cat, 1)
        self.d_suppr = QPushButton("Supprimer la dépense")
        self.d_suppr.setObjectName("danger")
        b.addWidget(self.d_suppr)
        l.addLayout(b)
        onglets.addTab(w, "Dépenses")

        self.t_ajout.clicked.connect(self._ajout_tempete)
        self.d_ajout.clicked.connect(self._ajout_depense)
        self.t_suppr.clicked.connect(lambda: self._supprimer("tempetes", self.tt))
        self.d_suppr.clicked.connect(lambda: self._supprimer("depenses", self.td))

    def rafraichir(self):
        db, s = self.app.db, self.app.saison
        res = db.resume(s)
        k = self.bande.kpis
        k[0].definir(f"{res['nb_tempetes']}", detail=f"Tempêtes, sur {self.app.p.tempetes_normales} prévues")
        k[1].definir(f"{res['cm_total']:.0f} cm")
        k[2].definir(f"{res['heures_total']:.1f} h".replace(".", ","))
        k[3].definir(argent(res["depenses"]))

        rangs = db.tempetes(s)
        self.tt.setRowCount(len(rangs))
        for i, r in enumerate(rangs):
            self.tt.setItem(i, 0, item(date_longue(r["date"]), r["id"], gras=True))
            self.tt.setItem(i, 1, ItemNum(r["cm"], f"{r['cm']:.0f} cm"))
            self.tt.setItem(i, 2, ItemNum(r["heures"], f"{r['heures']:.1f} h".replace(".", ",")))
            self.tt.setItem(i, 3, item(r["notes"]))

        rangs = db.depenses(s)
        self.td.setRowCount(len(rangs))
        cats: dict[str, float] = {}
        for i, r in enumerate(rangs):
            self.td.setItem(i, 0, item(date_longue(r["date"]), r["id"], gras=True))
            self.td.setItem(i, 1, item(r["categorie"]))
            self.td.setItem(i, 2, item(r["description"]))
            self.td.setItem(i, 3, ItemNum(r["montant"]))
            cats[r["categorie"]] = cats.get(r["categorie"], 0) + r["montant"]
        self.par_cat.setText("   ".join(f"{c} : {argent(m)}" for c, m in sorted(cats.items(), key=lambda x: -x[1])))

    def _ajout_tempete(self):
        avant = self.app.db.nb_visites_facturees(self.app.saison)
        self.app.db.ajouter_tempete(self.app.saison, self.t_date.date().toPython().isoformat(),
                                    self.t_cm.value(), self.t_h.value(), self.t_notes.text().strip())
        n = self.app.db.nb_visites_facturees(self.app.saison) - avant
        self.t_notes.clear()
        self.app.rafraichir()
        self.app.toast("Tempête ajoutée au journal." + (f" {n} visite{'s' * (n > 1)} à facturer ajoutée{'s' * (n > 1)} aux paiements." if n else ""))

    def _ajout_depense(self):
        if self.d_mnt.value() <= 0:
            QMessageBox.warning(self, "Montant manquant", "Entrez le montant de la dépense.")
            return
        self.app.db.ajouter_depense(self.app.saison, self.d_date.date().toPython().isoformat(),
                                    self.d_cat.currentText(), self.d_desc.text().strip(), self.d_mnt.value())
        self.d_desc.clear()
        self.d_mnt.setValue(0)
        self.app.rafraichir()
        self.app.toast("Dépense ajoutée.")

    def _supprimer(self, table, t):
        rid = id_selection(t)
        if rid and QMessageBox.question(self, "Supprimer", "Supprimer cette ligne ? Pour une tempête, les visites non payées qu'elle a facturées sont aussi retirées.") == QMessageBox.StandardButton.Yes:
            self.app.db.supprimer(table, rid)
            self.app.rafraichir()
