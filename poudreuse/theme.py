"""Identité visuelle de Poudreuse.

Inspirée de la nuit de déneigement : bitume, neige, gyrophare ambre des
charrues et piquets de balisage orange. Police : Barlow, dessinée d'après la
signalisation routière.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFontDatabase, QFont


def dossier_ressources() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    p = base / "poudreuse" / "ressources"
    return p if p.exists() else Path(__file__).resolve().parent / "ressources"


BITUME = "#263038"
BITUME_CLAIR = "#323E47"
BITUME_TEXTE = "#AEB9C1"
NEIGE = "#EEF1F3"
BLANC = "#FFFFFF"
SUIE = "#1C252C"
GRIS = "#5E6B75"
SEL = "#D5DCE1"
GYRO = "#F5A800"
GYRO_FONCE = "#C98A00"
BALISE = "#D9480F"
EPINETTE = "#2F7A55"

TEXTE = "Barlow"
TITRE = "Barlow Semi Condensed"


def charger_polices() -> None:
    dossier = dossier_ressources() / "polices"
    for f in dossier.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(f))


def police(taille: int = 10, poids: int = 400, titre: bool = False) -> QFont:
    f = QFont(TITRE if titre else TEXTE)
    f.setPointSizeF(taille)
    f.setWeight(QFont.Weight(poids))
    return f


QSS = f"""
* {{
    font-family: "{TEXTE}", "Segoe UI", sans-serif;
    font-size: 10.5pt;
    color: {SUIE};
}}
QMainWindow, QWidget#fond {{ background: {NEIGE}; }}
QToolTip {{ background: {BITUME}; color: {BLANC}; border: none; padding: 6px 8px; }}

/* ---------- barre latérale ---------- */
QWidget#barre {{ background: {BITUME}; }}
QLabel#marque {{
    font-family: "{TITRE}"; font-weight: 700; font-size: 20pt; color: {BLANC};
    padding: 22px 20px 2px 20px;
}}
QLabel#marqueSous {{ color: {BITUME_TEXTE}; font-size: 9.5pt; padding: 0 20px 22px 20px; }}
QPushButton#nav {{
    background: transparent; color: {BITUME_TEXTE}; border: none; border-left: 3px solid transparent;
    text-align: left; padding: 11px 17px; font-size: 11pt; font-weight: 500;
}}
QPushButton#nav:hover {{ background: {BITUME_CLAIR}; color: {BLANC}; }}
QPushButton#nav:checked {{ background: {BITUME_CLAIR}; color: {BLANC}; border-left: 3px solid {GYRO}; font-weight: 600; }}
QLabel#saisonBarre {{ color: {BITUME_TEXTE}; font-size: 9pt; padding: 0 20px; }}
QComboBox#saisonCombo {{
    background: {BITUME_CLAIR}; color: {BLANC}; border: 1px solid #44515B; margin: 4px 16px 20px 16px;
}}
QComboBox#saisonCombo QAbstractItemView {{ background: {BITUME_CLAIR}; color: {BLANC}; selection-background-color: {GYRO_FONCE}; }}

/* ---------- titres ---------- */
QLabel#titrePage {{ font-family: "{TITRE}"; font-weight: 700; font-size: 22pt; }}
QLabel#sousTitre {{ color: {GRIS}; font-size: 10.5pt; }}
QLabel#section {{ font-family: "{TITRE}"; font-weight: 600; font-size: 13pt; padding-top: 6px; }}
QLabel#aide {{ color: {GRIS}; font-size: 9.5pt; }}
QLabel#etiquette {{ color: {GRIS}; font-size: 9.5pt; }}

/* ---------- panneaux ---------- */
QFrame#panneau {{ background: {BLANC}; border: 1px solid {SEL}; border-radius: 6px; }}
QFrame#panneauSigne {{ background: {BITUME}; border-radius: 3px; }}
QFrame#panneauSigne QLabel {{ color: {BITUME_TEXTE}; }}
QFrame#panneauSigne QLabel#prixGeant {{ font-family: "{TITRE}"; font-weight: 700; font-size: 44pt; color: {GYRO}; }}
QFrame#panneauSigne QLabel#signeTitre {{ color: {BLANC}; font-weight: 600; font-size: 11pt; }}
QFrame#panneauSigne QLabel#signeValeur {{ color: {BLANC}; font-weight: 600; }}
QFrame#panneauSigne QLabel#signeAlerte {{ color: #FFB27A; }}
QFrame#ligneSigne {{ background: #3D4952; max-height: 1px; min-height: 1px; border: none; }}
QFrame#separateur {{ background: {SEL}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#separateurV {{ background: {SEL}; max-width: 1px; min-width: 1px; border: none; }}

QLabel#kpiValeur {{ font-family: "{TITRE}"; font-weight: 700; font-size: 21pt; }}
QLabel#kpiLibelle {{ color: {GRIS}; font-size: 9.5pt; }}
QLabel#kpiAlerte {{ font-family: "{TITRE}"; font-weight: 700; font-size: 21pt; color: {BALISE}; }}

/* ---------- champs ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QPlainTextEdit {{
    background: {BLANC}; border: 1px solid {SEL}; border-radius: 4px; padding: 6px 8px;
    selection-background-color: {GYRO}; selection-color: {SUIE};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {GYRO_FONCE};
}}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0px; border: none; }}
QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow {{ width: 0px; height: 0px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {BLANC}; border: 1px solid {SEL}; selection-background-color: #FFE7A8; selection-color: {SUIE}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid #A9B5BE; border-radius: 3px; background: {BLANC}; }}
QCheckBox::indicator:checked {{ background: {GYRO}; border: 1px solid {GYRO_FONCE}; }}

/* ---------- boutons ---------- */
QPushButton {{
    background: {BLANC}; border: 1px solid {SEL}; border-radius: 4px; padding: 8px 14px; font-weight: 500;
}}
QPushButton:hover {{ border-color: #A9B5BE; background: #F7F9FA; }}
QPushButton:pressed {{ background: {NEIGE}; }}
QPushButton:disabled {{ color: #A9B5BE; }}
QPushButton#principal {{ background: {GYRO}; border: 1px solid {GYRO_FONCE}; font-weight: 600; }}
QPushButton#principal:hover {{ background: #FFB81F; }}
QPushButton#principal:pressed {{ background: {GYRO_FONCE}; }}
QPushButton#principal:disabled {{ background: #F4E6C2; border-color: #E8D6A6; color: #A08A55; }}
QPushButton#danger {{ color: {BALISE}; }}
QPushButton#danger:hover {{ border-color: {BALISE}; }}
QPushButton#lien {{ border: none; background: transparent; color: {GYRO_FONCE}; padding: 4px; text-decoration: underline; }}

/* ---------- tableaux ---------- */
QTableWidget {{
    background: {BLANC}; border: 1px solid {SEL}; border-radius: 6px; gridline-color: transparent;
    alternate-background-color: #F8FAFB; selection-background-color: #FFF0C7; selection-color: {SUIE};
}}
QTableWidget::item {{ padding: 4px 8px; border-bottom: 1px solid #EDF0F2; }}
QHeaderView::section {{
    background: {BLANC}; color: {GRIS}; border: none; border-bottom: 1px solid {SEL};
    padding: 8px; font-weight: 600; font-size: 9.5pt;
}}
QTableCornerButton::section {{ background: {BLANC}; border: none; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #C3CCD3; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #C3CCD3; border-radius: 4px; min-width: 30px; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 8px 16px; color: {GRIS}; border-bottom: 2px solid transparent; font-weight: 500; }}
QTabBar::tab:selected {{ color: {SUIE}; border-bottom: 2px solid {GYRO}; font-weight: 600; }}

QSlider::groove:horizontal {{ height: 4px; background: {SEL}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {GYRO}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {BLANC}; border: 2px solid {GYRO_FONCE}; width: 14px; height: 14px; margin: -7px 0; border-radius: 9px; }}

QMessageBox QLabel {{ font-size: 10.5pt; }}
QDialog {{ background: {NEIGE}; }}
QLabel#toast {{ background: {BITUME}; color: {BLANC}; padding: 10px 16px; border-radius: 4px; font-weight: 500; }}
"""
