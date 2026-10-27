"""Fenêtre principale de Poudreuse."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QStandardPaths
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
                               QStackedWidget, QButtonGroup, QComboBox, QFileDialog, QMessageBox)

from . import theme, __version__
from .calculs import saison_courante
from .donnees import Base
from .widgets import Toast, etiquette
from .pages.tableau import PageTableau
from .pages.soumission import PageSoumission
from .pages.contrats import PageContrats
from .pages.paiements import PagePaiements
from .pages.rentabilite import PageRentabilite
from .pages.saison import PageSaison
from .pages.parametres import PageParametres

NAV = [
    ("tableau", "Tableau de bord"),
    ("soumission", "Nouvelle soumission"),
    ("contrats", "Clients et contrats"),
    ("paiements", "Paiements"),
    ("rentabilite", "Rentabilité"),
    ("saison", "Journal de la saison"),
    ("parametres", "Paramètres"),
]


class FenetrePrincipale(QMainWindow):
    def __init__(self, db: Base | None = None):
        super().__init__()
        self.db = db or Base()
        self.p = self.db.parametres()
        if not self.p.saison:
            self.p.saison = saison_courante()
        self.saison = self.p.saison

        self.setWindowTitle("Poudreuse")
        self.resize(1320, 860)
        self.setMinimumSize(1100, 700)
        icone = theme.dossier_ressources() / "poudreuse.png"
        if icone.exists():
            self.setWindowIcon(QIcon(str(icone)))

        central = QWidget()
        central.setObjectName("fond")
        self.setCentralWidget(central)
        racine = QHBoxLayout(central)
        racine.setContentsMargins(0, 0, 0, 0)
        racine.setSpacing(0)

        # Barre latérale
        barre = QWidget()
        barre.setObjectName("barre")
        barre.setFixedWidth(232)
        bl = QVBoxLayout(barre)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        bl.addWidget(etiquette("Poudreuse", "marque"))
        bl.addWidget(etiquette("Gestion de déneigement", "marqueSous"))
        self.groupe = QButtonGroup(self)
        self.boutons: dict[str, QPushButton] = {}
        for cle, libelle in NAV:
            b = QPushButton(libelle)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.groupe.addButton(b)
            self.boutons[cle] = b
            bl.addWidget(b)
            b.clicked.connect(lambda _=False, c=cle: self.aller(c))
        bl.addStretch()
        bl.addWidget(etiquette("Saison affichée", "saisonBarre"))
        self.combo_saison = QComboBox()
        self.combo_saison.setObjectName("saisonCombo")
        self.combo_saison.currentTextChanged.connect(self._combo_saison)
        bl.addWidget(self.combo_saison)
        bl.addWidget(etiquette(f"Version {__version__}", "saisonBarre"))
        bl.addSpacing(14)
        racine.addWidget(barre)

        # Pages
        self.pile = QStackedWidget()
        self.pages = {
            "tableau": PageTableau(self),
            "soumission": PageSoumission(self),
            "contrats": PageContrats(self),
            "paiements": PagePaiements(self),
            "rentabilite": PageRentabilite(self),
            "saison": PageSaison(self),
            "parametres": PageParametres(self),
        }
        for p in self.pages.values():
            self.pile.addWidget(p)
        racine.addWidget(self.pile, 1)

        self._toast = Toast(central)
        self._remplir_saisons()
        self.rafraichir()
        self.aller("tableau")

    # ------------------------------------------------------------ navigation
    def aller(self, cle: str):
        self.boutons[cle].setChecked(True)
        page = self.pages[cle]
        if hasattr(page, "rafraichir") and cle != "soumission":
            page.rafraichir()
        self.pile.setCurrentWidget(page)

    def nouvelle_soumission(self):
        self.pages["soumission"].reinitialiser()
        self.aller("soumission")

    def ouvrir_contrat(self, cid: int):
        self.pages["soumission"].charger(cid)
        self.aller("soumission")

    def rafraichir(self):
        for cle, page in self.pages.items():
            if cle != "soumission" and hasattr(page, "rafraichir"):
                page.rafraichir()
        self.pages["soumission"].recalculer()

    def toast(self, texte: str):
        self._toast.montrer(texte)

    # ------------------------------------------------------------ saisons
    def _remplir_saisons(self):
        saisons = set(self.db.saisons()) | {self.p.saison, self.saison, saison_courante()}
        self.combo_saison.blockSignals(True)
        self.combo_saison.clear()
        self.combo_saison.addItems(sorted(saisons, reverse=True))
        self.combo_saison.setCurrentText(self.saison)
        self.combo_saison.blockSignals(False)

    def _combo_saison(self, s: str):
        if s and s != self.saison:
            self.saison = s
            self.rafraichir()

    def changer_saison(self, s: str):
        if not re.fullmatch(r"\d{4}-\d{4}", s or ""):
            s = saison_courante()
        self.saison = s
        self._remplir_saisons()
        self.rafraichir()

    # ------------------------------------------------------------ documents
    def dossier_documents(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation) or str(Path.home())
        d = Path(base) / "Poudreuse"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _nom_fichier(texte: str) -> str:
        return re.sub(r"[^\w\- ]", "", texte).strip().replace(" ", "-") or "client"

    def _demander_pdf(self, nom: str) -> str | None:
        chemin, _ = QFileDialog.getSaveFileName(self, "Enregistrer le PDF", str(self.dossier_documents() / nom),
                                                "Document PDF (*.pdf)")
        if chemin and not chemin.lower().endswith(".pdf"):
            chemin += ".pdf"
        return chemin or None

    def pdf_contrat(self, cid: int, chemin: str | None = None, ouvrir: bool = True):
        import json
        from .calculs import Entree
        from . import pdf
        c = self.db.contrat(cid)
        if not c:
            return None
        type_doc = "contrat" if c["statut"] == "Signé" else "soumission"
        chemin = chemin or self._demander_pdf(f"{type_doc}-{self._nom_fichier(c['nom'])}-{c['saison']}.pdf")
        if not chemin:
            return None
        e = Entree.from_dict(json.loads(c["entree_json"]))
        vs = self.db.versements_contrat(cid) if c["statut"] == "Signé" else None
        try:
            pdf.soumission_ou_contrat(chemin, self.p, c, e, vs)
        except PermissionError:
            QMessageBox.warning(self, "Fichier ouvert", "Ce PDF est déjà ouvert dans un autre programme. Fermez-le et réessayez.")
            return None
        if ouvrir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(chemin))
        self.toast(f"PDF de la {type_doc} créé.")
        return chemin

    def pdf_recu(self, vid: int, chemin: str | None = None, ouvrir: bool = True):
        from . import pdf
        v = self.db.versement(vid)
        if not v:
            return None
        chemin = chemin or self._demander_pdf(f"recu-{self._nom_fichier(v['nom'])}-{v['no']}.pdf")
        if not chemin:
            return None
        c = self.db.contrat(v["cid"])
        deja = sum(x["montant"] for x in self.db.versements_contrat(v["cid"]) if x["paye"])
        pdf.recu(chemin, self.p, v, c["total"], deja)
        if ouvrir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(chemin))
        self.toast("Reçu créé.")
        return chemin


def lancer():
    if sys.platform == "win32":
        try:  # icône correcte dans la barre des tâches de Windows
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Poudreuse.Deneigement")
        except Exception:
            pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    from PySide6.QtCore import QLocale
    QLocale.setDefault(QLocale(QLocale.Language.French, QLocale.Country.Canada))
    app.setApplicationName("Poudreuse")
    app.setOrganizationName("Poudreuse")
    theme.charger_polices()
    app.setFont(theme.police(10.5))
    app.setStyle("Fusion")
    app.setStyleSheet(theme.QSS)
    f = FenetrePrincipale()
    f.show()
    sys.exit(app.exec())
