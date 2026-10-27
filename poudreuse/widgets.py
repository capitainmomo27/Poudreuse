"""Petites briques d'interface réutilisées par toutes les pages."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath, QBrush
from PySide6.QtWidgets import (QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QDoubleSpinBox, QSpinBox,
                               QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QSizePolicy)

from . import theme
from .calculs import argent


def etiquette(texte: str, nom: str = "etiquette") -> QLabel:
    l = QLabel(texte)
    l.setObjectName(nom)
    l.setWordWrap(True)
    return l


def entete_page(titre: str, sous_titre: str = "") -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 8)
    lay.setSpacing(2)
    lay.addWidget(etiquette(titre, "titrePage"))
    if sous_titre:
        lay.addWidget(etiquette(sous_titre, "sousTitre"))
    return w


class Panneau(QFrame):
    def __init__(self, marges: int = 18, espacement: int = 10, horizontal: bool = False):
        super().__init__()
        self.setObjectName("panneau")
        self.lay = (QHBoxLayout if horizontal else QVBoxLayout)(self)
        self.lay.setContentsMargins(marges, marges, marges, marges)
        self.lay.setSpacing(espacement)


def separateur(vertical: bool = False) -> QFrame:
    f = QFrame()
    f.setObjectName("separateurV" if vertical else "separateur")
    return f


def nombre(minimum=0.0, maximum=1e6, valeur=0.0, suffixe="", decimales=2, pas=1.0) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setLocale(_locale_fr())
    s.setRange(minimum, maximum)
    s.setDecimals(decimales)
    s.setSingleStep(pas)
    s.setValue(valeur)
    if suffixe:
        s.setSuffix(f" {suffixe}")
    s.setAlignment(Qt.AlignmentFlag.AlignRight)
    return s


def entier(minimum=0, maximum=100000, valeur=0, suffixe="") -> QSpinBox:
    s = QSpinBox()
    s.setRange(minimum, maximum)
    s.setValue(valeur)
    if suffixe:
        s.setSuffix(f" {suffixe}")
    s.setAlignment(Qt.AlignmentFlag.AlignRight)
    return s


def _locale_fr():
    from PySide6.QtCore import QLocale
    loc = QLocale(QLocale.Language.French, QLocale.Country.Canada)
    loc.setNumberOptions(QLocale.NumberOption.OmitGroupSeparator)
    return loc


class Kpi(QWidget):
    """Un chiffre et son libellé, sans boîte : on les aligne dans un même panneau."""
    def __init__(self, libelle: str):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.valeur = etiquette("–", "kpiValeur")
        self.valeur.setWordWrap(False)
        self.libelle = etiquette(libelle, "kpiLibelle")
        lay.addWidget(self.valeur)
        lay.addWidget(self.libelle)

    def definir(self, texte: str, alerte: bool = False, detail: str | None = None):
        self.valeur.setText(texte)
        self.valeur.setObjectName("kpiAlerte" if alerte else "kpiValeur")
        self.valeur.style().unpolish(self.valeur)
        self.valeur.style().polish(self.valeur)
        if detail is not None:
            self.libelle.setText(detail)


class BandeKpi(Panneau):
    def __init__(self, libelles: list[str]):
        super().__init__(marges=20, espacement=24, horizontal=True)
        self.kpis: list[Kpi] = []
        for i, l in enumerate(libelles):
            if i:
                self.lay.addWidget(separateur(vertical=True))
            k = Kpi(l)
            self.kpis.append(k)
            self.lay.addWidget(k, 1)


# --------------------------------------------------------------------------
# Tableaux
# --------------------------------------------------------------------------
class ItemNum(QTableWidgetItem):
    """Cellule triée selon sa valeur numérique et non selon son texte."""
    def __init__(self, valeur: float, texte: str | None = None):
        super().__init__(texte if texte is not None else argent(valeur))
        self.setData(Qt.ItemDataRole.UserRole + 1, float(valeur))
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        a = self.data(Qt.ItemDataRole.UserRole + 1)
        b = other.data(Qt.ItemDataRole.UserRole + 1)
        if a is not None and b is not None:
            return a < b
        return super().__lt__(other)


def tableau(colonnes: list[str], etirer: int = 0) -> QTableWidget:
    t = QTableWidget(0, len(colonnes))
    t.setHorizontalHeaderLabels(colonnes)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(38)
    t.setShowGrid(False)
    t.setAlternatingRowColors(True)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    h = t.horizontalHeader()
    h.setHighlightSections(False)
    h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    h.setSectionResizeMode(etirer, QHeaderView.ResizeMode.Stretch)
    return t


def item(texte, identifiant=None, couleur: str | None = None, gras: bool = False) -> QTableWidgetItem:
    it = QTableWidgetItem(str(texte) if texte is not None else "")
    if identifiant is not None:
        it.setData(Qt.ItemDataRole.UserRole, identifiant)
    if couleur:
        it.setForeground(QColor(couleur))
    if gras:
        f = it.font()
        f.setWeight(f.Weight.DemiBold)
        it.setFont(f)
    return it


def id_selection(t: QTableWidget):
    r = t.currentRow()
    if r < 0:
        return None
    it = t.item(r, 0)
    return it.data(Qt.ItemDataRole.UserRole) if it else None


# --------------------------------------------------------------------------
# Courbe de profit selon le nombre de tempêtes
# --------------------------------------------------------------------------
class CourbeProfit(QWidget):
    def __init__(self):
        super().__init__()
        self.points: list[tuple[int, float]] = []
        self.reperes: list[tuple[str, int]] = []
        self.actuel: int | None = None
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._survol: int | None = None

    def definir(self, points, reperes, actuel=None):
        self.points, self.reperes, self.actuel = points, reperes, actuel
        self.update()

    def _geo(self):
        g, d, h, b = 70, 20, 16, 34
        r = QRectF(g, h, max(self.width() - g - d, 10), max(self.height() - h - b, 10))
        ys = [p for _, p in self.points] or [0]
        ymin, ymax = min(min(ys), 0), max(max(ys), 0)
        if ymax == ymin:
            ymax = ymin + 1
        marge = (ymax - ymin) * 0.08
        ymin -= marge
        ymax += marge
        xmax = max((t for t, _ in self.points), default=1) or 1
        fx = lambda t: r.left() + t / xmax * r.width()
        fy = lambda v: r.bottom() - (v - ymin) / (ymax - ymin) * r.height()
        return r, fx, fy, ymin, ymax, xmax

    def mouseMoveEvent(self, ev):
        if not self.points:
            return
        r, fx, fy, *_ , xmax = self._geo()
        t = round((ev.position().x() - r.left()) / r.width() * xmax)
        self._survol = t if 0 <= t <= xmax else None
        self.update()

    def leaveEvent(self, ev):
        self._survol = None
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.points:
            p.setPen(QColor(theme.GRIS))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Signez des contrats pour voir la courbe de profit.")
            return
        r, fx, fy, ymin, ymax, xmax = self._geo()
        p.setFont(theme.police(9))

        # grille horizontale
        p.setPen(QPen(QColor("#E3E8EC"), 1))
        etapes = 5
        for i in range(etapes + 1):
            v = ymin + (ymax - ymin) * i / etapes
            y = fy(v)
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            p.setPen(QColor(theme.GRIS))
            p.drawText(QRectF(0, y - 9, r.left() - 8, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{v/1000:,.1f} k$".replace(",", " ").replace(".", ","))
            p.setPen(QPen(QColor("#E3E8EC"), 1))

        # axe X
        p.setPen(QColor(theme.GRIS))
        pas = 5 if xmax > 20 else 2
        for t in range(0, xmax + 1, pas):
            p.drawText(QRectF(fx(t) - 20, r.bottom() + 6, 40, 16), Qt.AlignmentFlag.AlignCenter, str(t))
        p.drawText(QRectF(r.left(), r.bottom() + 18, r.width(), 16), Qt.AlignmentFlag.AlignCenter, "tempêtes dans la saison")

        # zone sous zéro
        y0 = fy(0)
        p.fillRect(QRectF(r.left(), y0, r.width(), r.bottom() - y0), QColor(217, 72, 15, 18))
        p.setPen(QPen(QColor(theme.SUIE), 1))
        p.drawLine(QPointF(r.left(), y0), QPointF(r.right(), y0))

        # repères (hiver léger / normal / neigeux)
        for nom, t in self.reperes:
            x = fx(t)
            p.setPen(QPen(QColor("#A9B5BE"), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            p.setPen(QColor(theme.GRIS))
            p.drawText(QRectF(x + 4, r.top(), 140, 16), Qt.AlignmentFlag.AlignLeft, nom)

        # courbe
        chemin = QPainterPath()
        for i, (t, v) in enumerate(self.points):
            pt = QPointF(fx(t), fy(v))
            chemin.moveTo(pt) if i == 0 else chemin.lineTo(pt)
        p.setPen(QPen(QColor(theme.GYRO_FONCE), 2.5))
        p.drawPath(chemin)

        # point actuel / survol
        cible = self._survol if self._survol is not None else self.actuel
        if cible is not None and 0 <= cible < len(self.points):
            t, v = self.points[cible]
            pt = QPointF(fx(t), fy(v))
            p.setBrush(QBrush(QColor(theme.GYRO)))
            p.setPen(QPen(QColor(theme.BITUME), 2))
            p.drawEllipse(pt, 5, 5)
            texte = f"{t} tempêtes : {argent(v)}"
            p.setFont(theme.police(9.5, 600))
            largeur = p.fontMetrics().horizontalAdvance(texte) + 16
            bx = min(max(pt.x() - largeur / 2, r.left()), r.right() - largeur)
            by = pt.y() - 34 if pt.y() - 34 > r.top() else pt.y() + 12
            p.setBrush(QColor(theme.BITUME))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(bx, by, largeur, 24), 3, 3)
            p.setPen(QColor(theme.BLANC))
            p.drawText(QRectF(bx, by, largeur, 24), Qt.AlignmentFlag.AlignCenter, texte)


# --------------------------------------------------------------------------
# Notification discrète en bas de la fenêtre
# --------------------------------------------------------------------------
class Toast(QLabel):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.hide()
        self._minuterie = QTimer(self)
        self._minuterie.setSingleShot(True)
        self._minuterie.timeout.connect(self.hide)

    def montrer(self, texte: str, ms: int = 2600):
        self.setText(texte)
        self.adjustSize()
        par = self.parentWidget()
        self.move(par.width() - self.width() - 24, par.height() - self.height() - 24)
        self.raise_()
        self.show()
        self._minuterie.start(ms)
