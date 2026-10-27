"""Documents PDF : soumission, contrat et reçu de paiement."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether)

from .calculs import Parametres, Entree, TYPES_CONTRAT, argent, generer_versements
from .theme import dossier_ressources

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

ENCRE = colors.HexColor("#1C252C")
GRIS = colors.HexColor("#5E6B75")
FILET = colors.HexColor("#D5DCE1")
AMBRE = colors.HexColor("#F5A800")
BITUME = colors.HexColor("#263038")

_polices_ok = False


def _polices():
    global _polices_ok
    if _polices_ok:
        return
    d = dossier_ressources() / "polices"
    try:
        pdfmetrics.registerFont(TTFont("Barlow", str(d / "Barlow-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("Barlow-SemiBold", str(d / "Barlow-SemiBold.ttf")))
        pdfmetrics.registerFont(TTFont("Barlow-Titre", str(d / "BarlowSemiCondensed-Bold.ttf")))
    except Exception:
        # Repli sur les polices intégrées de reportlab
        pdfmetrics.registerFontFamily("Helvetica")
        for alias, base in (("Barlow", "Helvetica"), ("Barlow-SemiBold", "Helvetica-Bold"), ("Barlow-Titre", "Helvetica-Bold")):
            pdfmetrics._fonts[alias] = pdfmetrics.getFont(base)
    _polices_ok = True


def date_longue(d: date | str) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return f"{d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"


def _styles():
    _polices()
    return dict(
        corps=ParagraphStyle("corps", fontName="Barlow", fontSize=10, leading=14, textColor=ENCRE),
        petit=ParagraphStyle("petit", fontName="Barlow", fontSize=8.5, leading=12, textColor=GRIS),
        gras=ParagraphStyle("gras", fontName="Barlow-SemiBold", fontSize=10, leading=14, textColor=ENCRE),
        titre=ParagraphStyle("titre", fontName="Barlow-Titre", fontSize=24, leading=28, textColor=ENCRE),
        entreprise=ParagraphStyle("ent", fontName="Barlow-Titre", fontSize=15, leading=18, textColor=ENCRE),
        section=ParagraphStyle("section", fontName="Barlow-SemiBold", fontSize=11, leading=15, textColor=ENCRE,
                               spaceBefore=10, spaceAfter=4),
        droite=ParagraphStyle("droite", fontName="Barlow", fontSize=10, leading=14, textColor=ENCRE, alignment=2),
    )


def _entete(p: Parametres, titre: str, numero: str, quand: date, s) -> list:
    coord = [p.adresse, p.ville, p.telephone, p.courriel]
    coord = "<br/>".join(x for x in coord if x)
    gauche = [Paragraph(p.nom_entreprise or "Mon entreprise", s["entreprise"])]
    if coord:
        gauche.append(Paragraph(coord, s["petit"]))
    numeros = []
    if p.neq:
        numeros.append(f"NEQ {p.neq}")
    if p.inscrit_taxes and p.no_tps:
        numeros.append(f"TPS {p.no_tps}")
    if p.inscrit_taxes and p.no_tvq:
        numeros.append(f"TVQ {p.no_tvq}")
    if numeros:
        gauche.append(Paragraph(" &nbsp; ".join(numeros), s["petit"]))

    logo = None
    if p.logo and Path(p.logo).exists():
        try:
            img = Image(p.logo)
            ratio = img.imageWidth / max(img.imageHeight, 1)
            h = 18 * mm
            img.drawHeight, img.drawWidth = h, min(h * ratio, 45 * mm)
            logo = img
        except Exception:
            logo = None

    droite = [Paragraph(titre, ParagraphStyle("t", parent=s["titre"], alignment=2)),
              Paragraph(f"N° {numero}<br/>{date_longue(quand)}", s["droite"])]

    cols = [[logo, gauche, droite]] if logo else [[gauche, droite]]
    largeurs = [48 * mm, 62 * mm, 70 * mm] if logo else [104 * mm, 76 * mm]
    t = Table(cols, colWidths=largeurs)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    bande = Table([[""]], colWidths=[180 * mm], rowHeights=[2.2 * mm])
    bande.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AMBRE)]))
    return [bande, Spacer(1, 6 * mm), t, Spacer(1, 7 * mm)]


def _bloc_client(c, s) -> Table:
    lignes = [c["nom"]]
    adresse = ", ".join(x for x in (c["adresse"], c["ville"]) if x)
    if adresse:
        lignes.append(adresse)
    contact = "  ".join(x for x in (c["telephone"], c["courriel"]) if x)
    if contact:
        lignes.append(contact)
    t = Table([[Paragraph("Client", s["petit"])],
               [Paragraph("<br/>".join(lignes), s["corps"])]], colWidths=[180 * mm])
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return t


def description_services(e: Entree, p: Parametres) -> list[str]:
    surface = e.longueur_pi * e.largeur_pi
    d = [f"Déneigement de l'entrée de {e.longueur_pi:g} × {e.largeur_pi:g} pi ({surface:,.0f} pi²)".replace(",", " ")
         + f" — {e.methode.lower()}"]
    if e.trottoir_pi:
        d.append(f"Trottoir ou allée piétonne : {e.trottoir_pi:g} pi linéaires")
    if e.perrons:
        d.append(f"Perrons, marches ou balcons : {e.perrons}")
    if e.abrasif:
        d.append("Épandage d'abrasif au besoin")
    if e.repasse:
        d.append("Retour pour dégager le bourrelet laissé par la charrue municipale")
    if e.type_contrat == TYPES_CONTRAT[0]:
        d.append(f"Visites illimitées pour la saison, dès {p.seuil_cm} cm d'accumulation")
    elif e.type_contrat == TYPES_CONTRAT[1]:
        d.append(f"Jusqu'à {e.visites_incluses} visites incluses, dès {p.seuil_cm} cm d'accumulation")
    else:
        d.append(f"Service à la visite, sur appel ou dès {p.seuil_cm} cm d'accumulation")
    return d


def _tableau_prix(c, e: Entree, p: Parametres, s) -> Table:
    libelle = "Prix par visite" if e.type_contrat == TYPES_CONTRAT[2] else f"Contrat de déneigement, saison {c['saison']}"
    lignes = [[Paragraph("Description", s["petit"]), Paragraph("Montant", ParagraphStyle("x", parent=s["petit"], alignment=2))]]
    services = "<br/>".join(f"• {x}" for x in description_services(e, p))
    lignes.append([Paragraph(f"<font name='Barlow-SemiBold'>{libelle}</font><br/>{services}", s["corps"]),
                   Paragraph(argent(c["prix"] + (c["prix"] * e.rabais_pct / (100 - e.rabais_pct) if e.rabais_pct else 0)),
                             s["droite"])])
    if e.rabais_pct:
        avant = c["prix"] / (1 - e.rabais_pct / 100)
        lignes.append([Paragraph(f"Rabais de {e.rabais_pct:g} %", s["corps"]),
                       Paragraph(argent(-(avant - c["prix"])), s["droite"])])
    tot = [["Sous-total", argent(c["prix"])]]
    if p.inscrit_taxes:
        tot += [["TPS (5 %)", argent(c["tps"])], ["TVQ (9,975 %)", argent(c["tvq"])]]
    tot.append(["Total" + (" par visite" if e.type_contrat == TYPES_CONTRAT[2] else ""), argent(c["total"])])
    for i, (a, b) in enumerate(tot):
        st = s["gras"] if i == len(tot) - 1 else s["corps"]
        lignes.append([Paragraph(a, ParagraphStyle("r", parent=st, alignment=2)),
                       Paragraph(b, ParagraphStyle("r2", parent=st, alignment=2))])
    t = Table(lignes, colWidths=[140 * mm, 40 * mm])
    n = len(lignes)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, FILET),
        ("LINEBELOW", (0, n - len(tot) - 1), (-1, n - len(tot) - 1), 0.6, FILET),
        ("LINEABOVE", (0, n - 1), (-1, n - 1), 1.2, ENCRE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _tableau_versements(versements: list[tuple], s) -> Table:
    lignes = [[Paragraph("Versement", s["petit"]), Paragraph("Échéance", s["petit"]),
               Paragraph("Montant", ParagraphStyle("x", parent=s["petit"], alignment=2))]]
    for i, (ech, mnt, paye) in enumerate(versements, start=1):
        etat = " — reçu" if paye else ""
        lignes.append([Paragraph(f"{i}", s["corps"]), Paragraph(date_longue(ech) + etat, s["corps"]),
                       Paragraph(argent(mnt), s["droite"])])
    t = Table(lignes, colWidths=[30 * mm, 110 * mm, 40 * mm])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, FILET),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def _signatures(s, client: str) -> Table:
    t = Table([["", "", ""], [Paragraph(f"Signature du client — {client}", s["petit"]), "",
                              Paragraph("Signature de l'entreprise", s["petit"])],
               [Paragraph("Date :", s["petit"]), "", Paragraph("Date :", s["petit"])]],
              colWidths=[83 * mm, 14 * mm, 83 * mm], rowHeights=[16 * mm, None, None])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (0, 0), 0.8, ENCRE), ("LINEBELOW", (2, 0), (2, 0), 0.8, ENCRE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _pied(canvas, doc, texte):
    canvas.saveState()
    canvas.setFont("Barlow", 8)
    canvas.setFillColor(GRIS)
    canvas.drawString(15 * mm, 10 * mm, texte)
    canvas.drawRightString(letter[0] - 15 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def soumission_ou_contrat(chemin: str | Path, p: Parametres, c, e: Entree, versements=None) -> Path:
    """c : ligne de contrat (avec les champs du client). Le document devient un contrat une fois signé."""
    s = _styles()
    signe = c["statut"] == "Signé"
    titre = "Contrat" if signe else "Soumission"
    quand = date.fromisoformat((c["signe_le"] if signe and c["signe_le"] else c["cree_le"])[:10])
    numero = f"{c['saison'][:4]}-{c['id']:04d}"

    elems = _entete(p, titre, numero, quand, s)
    elems.append(_bloc_client(c, s))
    elems.append(Spacer(1, 6 * mm))
    elems.append(_tableau_prix(c, e, p, s))

    if e.type_contrat != TYPES_CONTRAT[2]:
        if versements:
            vs = [(v["echeance"], v["montant"], v["paye"]) for v in versements]
        else:
            vs = [(d, m, 0) for d, m in generer_versements(c["total"], e.nb_versements, c["saison"])]
        elems.append(Paragraph("Modalités de paiement", s["section"]))
        elems.append(_tableau_versements(vs, s))
        elems.append(Paragraph("Paiement par virement Interac, chèque ou comptant.", s["petit"]))

    elems.append(Paragraph("Conditions", s["section"]))
    elems.append(Paragraph(p.conditions.replace("{seuil}", str(p.seuil_cm)), s["corps"]))
    if not signe:
        elems.append(Spacer(1, 2 * mm))
        elems.append(Paragraph(f"Cette soumission est valide jusqu'au {date_longue(quand + timedelta(days=30))}. "
                               "Pour l'accepter, signez-la et retournez-la avec le premier versement.", s["corps"]))
    elems.append(KeepTogether([Spacer(1, 8 * mm), _signatures(s, c["nom"])]))

    chemin = Path(chemin)
    doc = SimpleDocTemplate(str(chemin), pagesize=letter, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=12 * mm, bottomMargin=18 * mm,
                            title=f"{titre} {numero} — {c['nom']}", author=p.nom_entreprise)
    pied = f"{p.nom_entreprise} — {titre.lower()} n° {numero}"
    doc.build(elems, onFirstPage=lambda cv, d: _pied(cv, d, pied), onLaterPages=lambda cv, d: _pied(cv, d, pied))
    return chemin


def recu(chemin: str | Path, p: Parametres, v, total_contrat: float, deja_paye: float) -> Path:
    s = _styles()
    numero = f"{v['saison'][:4]}-{v['cid']:04d}-{v['no']}"
    quand = date.fromisoformat(v["date_paiement"]) if v["date_paiement"] else date.today()
    elems = _entete(p, "Reçu", numero, quand, s)
    client = {"nom": v["nom"], "adresse": v["adresse"], "ville": v["ville"], "telephone": "", "courriel": v["courriel"]}
    elems.append(_bloc_client(client, s))
    elems.append(Spacer(1, 6 * mm))
    lignes = [
        ["Paiement reçu", (f"visite de déneigement du {date_longue(v['echeance'])}" if v["libelle"]
                           else f"versement {v['no']} du contrat de déneigement {v['saison']}")],
        ["Date du paiement", date_longue(quand)],
        ["Mode de paiement", v["mode"] or "—"],
        ["Montant reçu", argent(v["montant"])],
    ]
    if not v["libelle"]:
        lignes += [["Total du contrat", argent(total_contrat)],
                   ["Solde restant", argent(max(total_contrat - deja_paye, 0))]]
    t = Table([[Paragraph(a, s["petit"]), Paragraph(b, s["gras"] if a == "Montant reçu" else s["corps"])]
               for a, b in lignes], colWidths=[50 * mm, 130 * mm])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, FILET), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    elems.append(t)
    elems.append(Spacer(1, 8 * mm))
    elems.append(Paragraph("Merci de votre confiance !", s["corps"]))
    doc = SimpleDocTemplate(str(chemin), pagesize=letter, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=12 * mm, bottomMargin=18 * mm, title=f"Reçu {numero}", author=p.nom_entreprise)
    pied = f"{p.nom_entreprise} — reçu n° {numero}"
    doc.build(elems, onFirstPage=lambda cv, d: _pied(cv, d, pied), onLaterPages=lambda cv, d: _pied(cv, d, pied))
    return Path(chemin)
