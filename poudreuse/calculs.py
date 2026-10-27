"""Moteur de calcul de Poudreuse.

Toutes les fonctions ici sont « pures » : elles ne touchent ni à l'interface
ni à la base de données, ce qui les rend faciles à tester.

Principe de prix : on estime le temps réel passé chez le client à chaque
visite, on le convertit en coût (main-d'œuvre, équipement, carburant,
abrasif), on multiplie par le nombre de visites prévues dans la saison, on
ajoute une part des frais fixes, puis on applique la marge visée.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
import math

PI2_PAR_M2 = 10.7639

TPS = 0.05
TVQ = 0.09975

# --------------------------------------------------------------------------
# Méthodes de déblaiement
# --------------------------------------------------------------------------
# productivite : pieds carrés déblayés par minute
# installation : minutes perdues à chaque arrêt (stationner, manœuvrer, finir)
# facteur_equip : part du coût horaire d'équipement qui s'applique
# facteur_carbu : part de la consommation horaire de carburant qui s'applique
METHODES: dict[str, dict] = {
    "Tracteur avec souffleuse": dict(productivite=420, installation=4.0, facteur_equip=1.30, facteur_carbu=1.00),
    "Pick-up avec gratte": dict(productivite=320, installation=5.0, facteur_equip=1.00, facteur_carbu=1.00),
    "Souffleuse manuelle": dict(productivite=85, installation=3.0, facteur_equip=0.35, facteur_carbu=0.20),
    "Pelle (à la main)": dict(productivite=25, installation=2.0, facteur_equip=0.05, facteur_carbu=0.00),
}

TYPES_CONTRAT = [
    "Saisonnier – visites illimitées",
    "Saisonnier – visites limitées",
    "À la visite",
]


@dataclass
class Parametres:
    """Réglages de l'entreprise. Valeurs par défaut réalistes pour le Québec."""
    # Entreprise
    nom_entreprise: str = "Mon entreprise de déneigement"
    adresse: str = ""
    ville: str = ""
    telephone: str = ""
    courriel: str = ""
    neq: str = ""
    no_tps: str = ""
    no_tvq: str = ""
    logo: str = ""
    inscrit_taxes: bool = True

    # Coûts d'exploitation
    taux_horaire_mo: float = 28.0        # $/h par personne, charges incluses
    personnes_par_equipe: int = 1
    cout_equipement_h: float = 18.0      # $/h : amortissement, entretien, assurance
    prix_carburant_l: float = 1.65       # $/L
    conso_l_h: float = 9.0               # L/h en opération
    conso_l_100km: float = 16.0          # L/100 km sur la route
    cout_abrasif_kg: float = 0.35        # $/kg
    abrasif_kg_100pi2: float = 0.6       # kg par 100 pi²
    frequence_abrasif: float = 0.5       # part des visites où on épand
    frais_fixes_saison: float = 3500.0   # assurances, permis, publicité, préparation
    nb_clients_prevus: int = 50

    # Route
    minutes_entre_clients: float = 4.0
    km_entre_clients: float = 1.5
    km_depot_aller_retour: float = 10.0
    heures_max_tempete: float = 10.0

    # Saison et prix
    tempetes_normales: int = 25
    facteur_repasse: float = 1.25        # retour après le passage de la charrue
    marge_visee: float = 0.30
    prix_minimum: float = 350.0
    prix_minimum_visite: float = 30.0
    prime_a_la_visite: float = 1.5       # service sur appel : moins prévisible, plus cher
    seuil_cm: int = 5
    saison: str = ""
    conditions: str = (
        "Le service débute dès une accumulation de {seuil} cm et se termine après la "
        "dernière chute de la saison, au plus tard le 15 avril. L'entrée doit être "
        "dégagée de tout véhicule et obstacle lors du passage. Des piquets de "
        "balisage sont installés avant les premières neiges. L'entreprise n'est pas "
        "responsable des dommages aux objets non balisés ni des bancs de neige laissés "
        "par la municipalité entre deux passages. Tout versement en retard peut "
        "entraîner la suspension du service."
    )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Parametres":
        p = cls()
        for k, v in (d or {}).items():
            if hasattr(p, k):
                defaut = getattr(p, k)
                try:
                    if isinstance(defaut, bool):
                        v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "oui")
                    elif isinstance(defaut, int):
                        v = int(float(v))
                    elif isinstance(defaut, float):
                        v = float(v)
                    else:
                        v = str(v)
                except (TypeError, ValueError):
                    v = defaut
                setattr(p, k, v)
        if not p.saison:
            p.saison = saison_courante()
        return p


@dataclass
class Entree:
    """Ce que l'on déneige chez un client."""
    longueur_pi: float = 40.0
    largeur_pi: float = 20.0
    methode: str = "Pick-up avec gratte"
    trottoir_pi: float = 0.0             # pieds linéaires de trottoir / allée piétonne
    perrons: int = 0                     # perrons, marches ou balcons faits à la pelle
    abrasif: bool = False
    repasse: bool = True                 # retour pour le bourrelet de la charrue
    type_contrat: str = TYPES_CONTRAT[0]
    visites_incluses: int = 20
    frais_additionnels: float = 0.0
    rabais_pct: float = 0.0
    nb_versements: int = 2

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Entree":
        e = cls()
        for k, v in (d or {}).items():
            if hasattr(e, k):
                setattr(e, k, type(getattr(e, k))(v))
        return e


@dataclass
class Ligne:
    libelle: str
    montant: float


@dataclass
class Resultat:
    surface_pi2: float
    surface_m2: float
    minutes_visite: float
    cout_visite: float
    visites_prevues: float
    cout_variable_saison: float
    part_frais_fixes: float
    cout_total: float
    prix_calcule: float
    prix: float               # prix final avant taxes (arrondi, minimum, rabais)
    prix_par_visite: float
    tps: float
    tvq: float
    total: float
    profit: float
    marge_reelle: float
    detail_visite: list[Ligne] = field(default_factory=list)
    scenarios: list[tuple[str, int, float]] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Outils
# --------------------------------------------------------------------------
def arrondi_argent(x: float) -> float:
    return float(f"{x + 1e-9:.2f}") if x >= 0 else -arrondi_argent(-x)


def arrondi_vente(x: float, pas: float = 5.0) -> float:
    """Arrondit un prix de vente au 5 $ supérieur (440,12 → 445)."""
    if x <= 0:
        return 0.0
    return math.ceil(x / pas - 1e-9) * pas


def taxes(montant: float, inscrit: bool = True) -> tuple[float, float, float]:
    """Retourne (TPS, TVQ, total). La TVQ se calcule sur le montant avant TPS."""
    if not inscrit:
        return 0.0, 0.0, arrondi_argent(montant)
    tps = arrondi_argent(montant * TPS)
    tvq = arrondi_argent(montant * TVQ)
    return tps, tvq, arrondi_argent(montant + tps + tvq)


def saison_courante(aujourdhui: date | None = None) -> str:
    d = aujourdhui or date.today()
    debut = d.year if d.month >= 7 else d.year - 1
    return f"{debut}-{debut + 1}"


def argent(x: float) -> str:
    """Format québécois : 1 234,56 $"""
    s = f"{abs(x):,.2f}".replace(",", " ").replace(".", ",")
    return f"{'-' if x < 0 else ''}{s} $"


# --------------------------------------------------------------------------
# Calculs principaux
# --------------------------------------------------------------------------
def minutes_par_visite(e: Entree, p: Parametres) -> float:
    m = METHODES.get(e.methode, METHODES["Pick-up avec gratte"])
    surface = max(e.longueur_pi, 0) * max(e.largeur_pi, 0)
    minutes = m["installation"] + surface / m["productivite"]
    minutes += max(e.trottoir_pi, 0) / 15.0          # souffleuse manuelle, ~15 pi lin/min
    minutes += max(e.perrons, 0) * 3.5               # pelle + balai
    if e.abrasif:
        minutes += 1.5 * p.frequence_abrasif
    return minutes


def cout_par_visite(e: Entree, p: Parametres) -> tuple[float, list[Ligne]]:
    m = METHODES.get(e.methode, METHODES["Pick-up avec gratte"])
    minutes_travail = minutes_par_visite(e, p)
    minutes_total = minutes_travail + p.minutes_entre_clients
    h = minutes_total / 60.0
    h_travail = minutes_travail / 60.0

    mo = h * p.taux_horaire_mo * max(p.personnes_par_equipe, 1)
    equip = h * p.cout_equipement_h * m["facteur_equip"]
    carbu = (h_travail * p.conso_l_h * m["facteur_carbu"]
             + p.km_entre_clients * p.conso_l_100km / 100.0) * p.prix_carburant_l
    surface = max(e.longueur_pi, 0) * max(e.largeur_pi, 0)
    abr = 0.0
    if e.abrasif:
        abr = (surface + e.trottoir_pi * 4) / 100.0 * p.abrasif_kg_100pi2 * p.cout_abrasif_kg * p.frequence_abrasif

    lignes = [
        Ligne("Main-d'œuvre", mo),
        Ligne("Équipement", equip),
        Ligne("Carburant", carbu),
    ]
    if abr:
        lignes.append(Ligne("Abrasif", abr))
    return mo + equip + carbu + abr, lignes


def visites_saison(e: Entree, p: Parametres, tempetes: float | None = None) -> float:
    t = p.tempetes_normales if tempetes is None else tempetes
    v = t * (p.facteur_repasse if e.repasse else 1.0)
    if e.type_contrat == TYPES_CONTRAT[1]:
        v = min(v, e.visites_incluses)
    return v


def calculer(e: Entree, p: Parametres) -> Resultat:
    surface = max(e.longueur_pi, 0) * max(e.largeur_pi, 0)
    minutes = minutes_par_visite(e, p)
    cout_v, lignes = cout_par_visite(e, p)
    visites = visites_saison(e, p)
    part_fixe = p.frais_fixes_saison / max(p.nb_clients_prevus, 1)
    cout_var = cout_v * visites
    cout_total = cout_var + part_fixe + e.frais_additionnels

    marge = min(max(p.marge_visee, 0.0), 0.9)
    prix_calc = cout_total / (1 - marge)

    # Prix à la visite : coût d'une visite + part des frais fixes étalée sur les visites normales
    visites_norm = max(visites_saison(Entree(**{**e.to_dict(), "type_contrat": TYPES_CONTRAT[0]}), p), 1)
    prix_visite = arrondi_vente((cout_v + part_fixe / visites_norm) / (1 - marge) * p.prime_a_la_visite, 1.0)
    prix_visite = max(prix_visite, p.prix_minimum_visite)

    avert: list[str] = []
    if e.type_contrat == TYPES_CONTRAT[2]:
        prix = prix_visite
        cout_ref = cout_v + part_fixe / visites_norm
    else:
        prix = arrondi_vente(prix_calc)
        if prix < p.prix_minimum:
            prix = p.prix_minimum
            avert.append(f"Prix relevé au minimum de l'entreprise ({argent(p.prix_minimum)}).")
        cout_ref = cout_total

    if e.rabais_pct:
        prix = arrondi_argent(prix * (1 - e.rabais_pct / 100.0))

    tps, tvq, total = taxes(prix, p.inscrit_taxes)
    profit = prix - cout_ref
    marge_reelle = profit / prix if prix else 0.0

    if marge_reelle < 0.10:
        avert.append("Marge sous 10 % : ce contrat rapporte très peu.")
    if minutes > 30:
        avert.append("Plus de 30 minutes par visite : vérifiez que la méthode choisie convient.")

    scenarios = []
    if e.type_contrat != TYPES_CONTRAT[2]:
        for nom, f in (("Hiver léger", 0.75), ("Hiver normal", 1.0), ("Hiver très neigeux", 1.4)):
            t = round(p.tempetes_normales * f)
            c = cout_v * visites_saison(e, p, t) + part_fixe + e.frais_additionnels
            scenarios.append((nom, t, prix - c))

    return Resultat(
        surface_pi2=surface,
        surface_m2=surface / PI2_PAR_M2,
        minutes_visite=minutes,
        cout_visite=cout_v,
        visites_prevues=visites,
        cout_variable_saison=cout_var,
        part_frais_fixes=part_fixe,
        cout_total=cout_ref,
        prix_calcule=prix_calc,
        prix=prix,
        prix_par_visite=prix_visite,
        tps=tps, tvq=tvq, total=total,
        profit=profit,
        marge_reelle=marge_reelle,
        detail_visite=lignes,
        scenarios=scenarios,
        avertissements=avert,
    )


# --------------------------------------------------------------------------
# Versements
# --------------------------------------------------------------------------
def generer_versements(total: float, nb: int, saison: str, signature: date | None = None) -> list[tuple[date, float]]:
    """Échéancier : 1er versement à la signature, les suivants le 15 du mois,
    à partir de décembre (2 versements : signature + 15 janvier)."""
    nb = max(1, min(int(nb), 6))
    signature = signature or date.today()
    try:
        annee_debut = int(saison.split("-")[0])
    except (ValueError, IndexError):
        annee_debut = signature.year if signature.month >= 7 else signature.year - 1

    mois_possibles = [(annee_debut, 12), (annee_debut + 1, 1), (annee_debut + 1, 2), (annee_debut + 1, 3)]
    if nb == 2:
        dates_suiv = [(annee_debut + 1, 1)]
    else:
        dates_suiv = mois_possibles[: nb - 1]
        while len(dates_suiv) < nb - 1:  # au-delà de 4 versements : mois suivants
            a, m = dates_suiv[-1]
            dates_suiv.append((a + (m == 12), m % 12 + 1))

    base = math.floor(total / nb * 100) / 100
    montants = [base] * nb
    montants[-1] = arrondi_argent(total - base * (nb - 1))

    echeances = [signature] + [max(date(a, m, 15), signature) for a, m in dates_suiv]
    return list(zip(echeances, montants))


# --------------------------------------------------------------------------
# Rentabilité de la saison (route complète)
# --------------------------------------------------------------------------
@dataclass
class Rentabilite:
    nb_contrats: int
    revenus: float
    minutes_tempete: float
    heures_tempete: float
    km_tempete: float
    cout_tempete: float
    frais_fixes: float
    seuil_tempetes: float
    courbe: list[tuple[int, float]]
    profit_normal: float
    equipes_requises: int


def rentabilite_saison(contrats: list[dict], p: Parametres, tempetes_max: int = 45) -> Rentabilite:
    """contrats : liste de dict avec 'entree' (Entree) et 'prix' (avant taxes).
    Les contrats à la visite rapportent prix × visites."""
    min_tot = 0.0
    km = p.km_depot_aller_retour
    cout_t = 0.0
    revenus_fixes = 0.0
    revenu_par_tempete = 0.0
    for c in contrats:
        e: Entree = c["entree"]
        cv, _ = cout_par_visite(e, p)
        rep = p.facteur_repasse if e.repasse else 1.0
        min_tot += (minutes_par_visite(e, p) + p.minutes_entre_clients) * rep
        km += p.km_entre_clients * rep
        cout_t += cv * rep
        if e.type_contrat == TYPES_CONTRAT[2]:
            revenu_par_tempete += c["prix"] * rep
        else:
            revenus_fixes += c["prix"]
    # trajet aller-retour au dépôt
    cout_t += p.km_depot_aller_retour * p.conso_l_100km / 100.0 * p.prix_carburant_l

    def profit(t: int) -> float:
        cout_var = 0.0
        rev_var = revenu_par_tempete * t
        for c in contrats:
            e: Entree = c["entree"]
            cv, _ = cout_par_visite(e, p)
            cout_var += cv * visites_saison(e, p, t)
        cout_var += p.km_depot_aller_retour * p.conso_l_100km / 100.0 * p.prix_carburant_l * t
        return revenus_fixes + rev_var - cout_var - p.frais_fixes_saison

    courbe = [(t, profit(t)) for t in range(0, tempetes_max + 1)]

    # Seuil : nombre de tempêtes à partir duquel la saison devient déficitaire.
    # 0 = les revenus ne couvrent même pas les frais fixes ; inf = jamais dans l'intervalle.
    seuil = float("inf")
    for t, pr in courbe:
        if pr < 0:
            seuil = t
            break

    heures = min_tot / 60.0
    equipes = max(1, math.ceil(heures / max(p.heures_max_tempete, 1))) if contrats else 0
    return Rentabilite(
        nb_contrats=len(contrats),
        revenus=revenus_fixes + revenu_par_tempete * p.tempetes_normales,
        minutes_tempete=min_tot,
        heures_tempete=heures,
        km_tempete=km if contrats else 0.0,
        cout_tempete=cout_t if contrats else 0.0,
        frais_fixes=p.frais_fixes_saison,
        seuil_tempetes=seuil,
        courbe=courbe,
        profit_normal=profit(p.tempetes_normales),
        equipes_requises=equipes,
    )
