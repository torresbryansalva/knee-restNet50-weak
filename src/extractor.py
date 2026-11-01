"""Extractor de etiquetas débiles (Paso 7) — versión final consolidada.

Reglas diseñadas SOLO con la muestra de 100 estudios elegibles NO gold (Paso 5.1).
Uso:
    from extractor import extraer_etiquetas
    extraer_etiquetas(reporte_norm)  # -> {etiqueta: 1 / 0 / -1} para las 12 etiquetas

Cada patrón aparece una sola vez, ya con todas las correcciones hechas durante el desarrollo
(7.3 -> 7.11) y las 2 correcciones de implementación vistas en el Paso 8.2:
  - fuera_de_la_articulacion(): la ventana de E2 cortaba "suprapatellar" y dejaba "bursada"
    (54 estudios turcos cambian).
  - INCIERTO: faltaba el griego "μπορούσε" (= podría) -> 1 estudio griego de Fracture pasa de 1 a -1.

─── REGLAS GENERALES (decididas el 2026-10-02; van al informe) ─────────────────────────────────────────
 D1. Salida por etiqueta: 1 = positivo, 0 = negativo, -1 = incierto ("posible", "no se descarta").
     El -1 se guarda para la ablación de "manejo de etiquetas ruidosas" (tratarlo como 0, como 1 o ignorarlo).
 D2. Hallazgo NO mencionado -> 0 (el radiólogo reporta lo anormal). Es una suposición: se mide en la validación.
 D3. Unidad de análisis = la oración: la negación y la duda se buscan en la misma oración que el hallazgo.
 D4. Se busca en minúsculas y sin tildes (para_buscar).
 D5. Fuente de texto = REPORTE COMPLETO para las 12 etiquetas (la conclusión omite hallazgos "acompañantes").
 D6. Las oraciones de ANTECEDENTES o INDICACIÓN ("antecedentes clínicos:", "clinical history:",
     "klinische inlichtingen:") no son hallazgos de esta RM -> se ignoran.
 Duda: la palabra de duda cuenta si va ANTES de la mención; DESPUÉS solo cuentan las dudas que se escriben
     detrás ("no se descarta", turco "telkin ediyor"/"düşündüren"). Así "contusion probablement résiduelle" es 1.
────────────────────────────────────────────────────────────────────────────────────────────────────────
"""
import re
import unicodedata

LABELS = ["ACL", "MCL", "Medial Meniscus", "Lateral Meniscus",
          "Medial OA", "Lateral OA", "PF OA", "Effusion",
          "Synovitis", "Baker's", "Contusion", "Fracture"]

ORDEN = {1: 2, -1: 1, 0: 0}          # en una oración y en un estudio manda el 1, luego el -1


# ══════════════════════════════════════════════════════════════════════════════════════════════════════
#  PIEZAS COMUNES
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
def para_buscar(texto):
    """D4: minúsculas y sin tildes, para que 'πρόσθιος' y 'ΠΡΟΣΘΙΟΣ' (o 'cruzado' con o sin tilde) coincidan."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c))
    return sin_tildes.lower()


def regex(*partes):
    """Une las alternativas con | y deja que cada espacio sea 1 o más espacios/saltos ("anterior  cruciate")."""
    return re.compile("|".join(partes).replace(" ", r"\s+"))


def oraciones(texto):
    """D3. Corta en:
        . ; ! ? + espacio  (salvo abreviaturas de una LETRA: "v. a."; un número sí corta: "grade 3. ...")
        punto pegado a una letra ("cekmistir.on") o tras paréntesis (").patellar")
        línea en blanco, o salto de línea que abre una viñeta (-, *, >, "1.", "acl:")
    NO corta en ':' ("acl: tear") ni en un salto de línea simple (el croata trae saltos dentro de la oración).
    """
    corte = (r"(?<!\b[^\W\d]\.)(?<=[.;!?])\s+"
             r"|(?<=\w{2}\.)(?=[^\W\d_])"
             r"|(?<=\)\.)(?=[^\W\d_])"
             r"|\n\s*\n"
             r"|\n(?=\s*(?:[-*•>]|\d+[.)]|\w{2,5}\s*:))")
    return [" ".join(o.split()) for o in re.split(corte, texto) if o.strip()]


ANTECEDENTES = regex(r"^\W*(antecedentes|clinical (history|information|indication)|history|indication|indicacion"
                     r"|klinische inlichtingen|vraagstelling|klinik|endikasyon|anamne|клинични данни|ιστορικο"
                     r"|fragestellung|renseignements cliniques|indications?)\b")                   # D6


def es_antecedente(o):
    return bool(ANTECEDENTES.search(o))


# Vocabulario común a todas las etiquetas (se aplica a todos los idiomas a la vez: langdetect puede fallar)
ROTURA = regex(r"\btear", r"\btorn\b", r"ruptur", r"disrupt", r"discontinu", r"deficien",            # en
               r"rotura", r"\broto\b", r"desgarr",                                                   # es
               r"y[iı]rt[iı][kg]", r"\bkopu",                     # tr (yırtık -> yırtığı; rüptür ya entra en "ruptur")
               r"puknu", r"prekid\w* kontinuitet",                                                   # hr
               r"ρηξη",                                                                              # el
               r"\briss", r"\w+riss\b",                                                              # de (Riss, Einriss, Teilriss)
               r"scheur",                                                                            # nl
               r"dechir", r"\brompu",                                                                # fr
               r"скъсван", r"руптур")                                                                # bg

NEGACION = regex(r"\bno\b", r"\bnot\b", r"without", r"negative for",                                 # en / es "no"
                 r"\bsin\b", r"\bkein", r"\bohne\b", r"\bgeen\b", r"\bzonder\b",                     # es, de, nl
                 r"\bpas de\b", r"\bsans\b", r"absence de",                                          # fr
                 r"\bbez\b", r"\bnema\b", r"\bδεν\b", r"χωρις", r"\bбез\b", r"\bняма\b", r"\bне се\b",
                 r"\bne\b", r"\bне\b",                    # hr / bg: el "no" va suelto ("ne nalazi se ... izljeva")
                 r"\baucun")                              # fr: "kyste de Baker : aucun"

# Negaciones que van DETRÁS de la mención. El turco niega con sufijo: "izlenmedi"/"izlenmemiştir" = no se observa,
# pero "izlenmektedir" = SE observa; por eso se exige la -d/-m tras "izlenme", "saptanma"...
NEGACION_TR = regex(r"izlenme[dm]", r"saptanma[dm]", r"gozlenme[dm]", r"rastlanma[dm]", r"\byok",
                    r"(is|are) not (seen|identified|visualized|present)", r"\babsent\b",
                    r"ausente", r"nicht nachweisbar", r"niet zichtbaar", r"\babsente?\b")

INCIERTO = regex(r"possibl", r"probabl", r"suspect", r"suspicio", r"cannot be (excluded|ruled out)",
                 r"likely", r"questionab", r"equivocal",                                             # en (+ fr probable/possible)
                 r"posible", r"sospech", r"no se descarta",                                          # es
                 r"supheli", r"olas[iı]", r"dusundur",                                               # tr
                 r"moguc", r"vjerojatn", r"sumnj",                                                   # hr
                 r"πιθαν", r"ενδεχομεν", r"υποψια",                                                  # el
                 r"\bv\. ?a\.", r"verdacht", r"moglich", r"wahrscheinlich",                          # de
                 r"mogelijk", r"waarschijnlijk", r"vermoedelijk",                                    # nl
                 r"вероятн", r"възможн", r"съмнени",                                                 # bg
                 r"telkin", r"\br/o\b",                                       # tr "telkin ediyor" = sugiere; en "r/o"
                 r"\bmaybe\b", r"\bmay be\b", r"\bcould\b", r"podria", r"\bkann\b",
                 r"\bmoze\b", r"\bkan\b", r"\bpeut\b", r"μπορει", r"μπορουσ", r"може би")   # μπορούσε = podría

# Dudas que se escriben DETRÁS de la mención
INCIERTO_DESPUES = regex(r"telkin", r"dusundur", r"supheli", r"olas[iı]", r"ekarte edilemez",       # tr
                         r"cannot be (excluded|ruled out)", r"not (be )?excluded", r"no se descarta",
                         r"ne moze se iskljuc", r"nicht auszuschlie", r"niet uit te sluiten",
                         r"ne peut etre exclu", r"не може да се изключи", r"δεν αποκλειεται", r"\?",
                         r"olabilecek", r"olabilir")                                  # K5 (tr: "podría ser")

NORMAL = regex(r"normal", r"intact", r"unremarkable", r"preserved",                                  # en / fr / nl / tr "normal"
               r"integr", r"sin alteracion", r"conservad", r"continuo",                              # es
               r"korunmus", r"saglam", r"\bintakt",                                                  # tr / de
               r"uredn", r"odrzan\w* kontinuitet", r"primjeren",                                     # hr
               r"φυσιολογικ", r"αθικτ",                                                              # el
               r"unauffallig", r"regelrecht",                                                        # de
               r"нормалн", r"запазен", r"интактн",                                                   # bg
               r"χωρις παθολογικ", r"δεν παρατηρουνται αξιολογα", r"\bodrzan",   # normalidad "en grupo" (el / hr)
               r"erhalten", r"homogen")                                           # de "erhaltener Knorpelbelag"

LESION = regex(r"injur", r"sprain", r"strain", r"laxit", r"lesion", r"esguince", r"distension",     # en / es / fr
               r"lezyon", r"hasar", r"laksite",                                                     # tr
               r"ozljed", r"lezij", r"\bedem", r"smanjen\w* napetost",                              # hr
               r"κακωση", r"οιδημ", r"θλαση",                                                       # el
               r"lasion", r"zerrung", r"distorsion",                                                # de (Läsion, Partialläsion)
               r"letsel", r"verstuik", r"entorse",                                                  # nl / fr
               r"травм", r"увреждан", r"оток", r"дисторз")                                          # bg


def negado(o, m):
    """¿Está negada la mención m? Negación antes (todos), después (turco/inglés) o tras ':' (formato hallazgo: valor)."""
    despues = o[m.end():]
    dos_puntos = re.match(r"[^.:]{0,30}:", despues)
    return bool(NEGACION.search(o[:m.start()]) or NEGACION_TR.search(despues)
                or (dos_puntos and NEGACION.search(despues[dos_puntos.end():])))


def dudoso(o, m):
    """Duda ANTES de la mención, o una duda "de las que van detrás" pegada a ella (≤ 40 caracteres)."""
    return bool(INCIERTO.search(o[:m.start()]) or INCIERTO_DESPUES.search(o[m.end():m.end() + 40]))


def lo_mas_fuerte(resultados):
    """De varias (etiqueta, motivo) de una misma oración, manda el 1, luego el -1; None si no hay ninguna."""
    return max(resultados, key=lambda r: ORDEN[r[0]]) if resultados else None


def etiqueta_estudio(etiquetas):
    """Un estudio puede tener varias oraciones sobre una etiqueta: manda el 1, luego el -1; sin menciones -> 0 (D2)."""
    if 1 in etiquetas:
        return 1
    return -1 if -1 in etiquetas else 0


# ══════════════════════════════════════════════════════════════════════════════════════════════════════
#  ACL (LCA)
#  L1. Rotura PARCIAL del LCA = 1 (lesión estructural real, visible en RM).
#  L2. Degeneración mucoide/mixoide, quiste gangliónico e hipoplasia del LCA NO son rotura -> 0.
#  L3. Lesión SIN palabra de rotura ("grade 1 injury", "partial injury", esguince, edema con laxitud) -> -1.
#  L4. Oración que menciona el LCA sin rotura, sin lesión y sin normalidad -> 0 (coherente con D2).
#  El LCA también se nombra "en grupo" ("ligamentos cruzados", "Kreuzbänder"): lo dicho del grupo vale para el LCA.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
LCA_SOLO = regex(r"\bacl\b", "anterior cruciate", "cruzado anterior", r"\blca\b", "croise anterieur",
                 "on capraz", "anterior capraz", r"prednj\w* kriz\w*", r"προσθι\w* χιαστ\w*",
                 r"vorder\w* (und hinter\w* )?kreuzband", r"\bvkb\b", "voorste kruisband", r"предн\w* кръстн\w*")
CRUZADOS = regex(r"cruciate (and \w+ )?ligaments", "ligamentos cruzados", "ligaments croises", "capraz baglar",
                 r"kriz\w* ligament(i|e|a)\b", "kriznih ligamenata", "χιαστοι", "χιαστων", "kreuzbander",
                 "kruisbanden", r"кръстн\w* връзки")
NO_ES_ROTURA_LCA = regex(r"mucoid", r"mukoid", r"mixoid", r"miksoid", r"μυξοειδ", r"мукоидн",
                         r"gangli", r"γαγγλι", r"hipoplas", r"hypoplas", r"хипопласт")


def clasificar_lca(o):
    if not (LCA_SOLO.search(o) or CRUZADOS.search(o)):
        return None
    m = ROTURA.search(o)
    if m:
        if negado(o, m):
            return 0, "rotura negada"
        return (-1, "rotura incierta") if dudoso(o, m) else (1, "rotura")
    if NO_ES_ROTURA_LCA.search(o):
        return 0, "no es rotura (L2)"
    if NORMAL.search(o):
        return 0, "normal"
    m = LESION.search(o)
    if m and not negado(o, m):
        return -1, "lesión sin rotura (L3)"
    return 0, "sin evidencia (L4)"


# ══════════════════════════════════════════════════════════════════════════════════════════════════════
#  EFFUSION
#  E1. Grado (una pequeña cantidad de líquido es NORMAL en la rodilla):
#        "fisiológico" / "cantidad normal" -> 0 · "mínimo", "trazas", "pequeño" -> -1 · leve/moderado/sin grado -> 1.
#      Si aparecen dos grados manda el mayor ("small-to-moderate" -> 1). El grado se busca pegado a la mención
#      y sin cruzar una coma.
#  E2. Solo cuenta el líquido INTRAARTICULAR (incluido el receso/bursa suprapatelar). Líquido en otra bursa,
#      quiste, prepatelar/subcutáneo o alrededor de un ligamento -> esa mención se ignora.
#  E3. Formato "hallazgo: valor" ("épanchement articulaire : pas de liquide"): negación tras los dos puntos.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
DERRAME = regex(r"effusion", r"hemarthro", r"(joint|intra-?articular) fluid", r"fluid in the (knee|joint)",      # en
                r"derrame", r"hidrartro", r"hemartro", r"liquido articular",                                   # es
                r"efuzyon", r"eklem\w* (ici )?s[iı]v[iı]", r"s[iı]v[iı] art[iı]s[iı]", r"s[iı]v[iı] miktar",  # tr
                r"izljev", r"hidrops",                                                                         # hr
                r"συλλογη υγρου", r"υδαρθρ", r"υδραρθρ", r"αιμαρθρ",                                           # el
                r"erguss", r"gelenkflussigkeit",                                                               # de
                r"hydrops", r"gewrichtsvocht", r"effusie",                                                     # nl
                r"epanchement", r"hydarthrose",                                                                # fr
                r"излив", r"ставна течност")                                                                   # bg
NO_ARTICULAR = regex(r"\bburs(?!\w* suprapatel)", r"\bburz", r"prepatel", r"prapatel", r"subkutan", r"subcutan",
                     r"baker", r"poplit", r"cist", r"cyst", r"kyst", r"zyst", r"κυστ", r"кист",
                     r"collateral", r"kollateral", r"\bmcl\b", r"\blcl\b")
FISIOLOGICO = regex(r"physiolog", r"fizyolojik", r"fiziolos", r"φυσιολογικ", r"fysiolog", r"физиологичн",
                    r"normal amount", r"cantidad normal")
POCO = regex(r"minim", r"trace", r"\bsmall", r"tiny", r"\bminor",                       # en / es / de / nl / fr "minim..."
             r"escas", r"pequen", r"trazas", r"\baz miktar",                            # es / tr
             r"\bmanj", r"\bmal\w* kolicin",                                            # hr
             r"ελαχιστ", r"μικρ", r"ιχνη",                                              # el
             r"gering", r"\bklein", r"\bspur",                                          # de / nl ("kleine hydrops")
             r"\bbeetje", r"\bpetit", r"\bfaible",                                      # nl / fr
             r"малък", r"малко", r"минимал", r"незначителн")                            # bg
MUCHO = regex(r"moderat", r"\blarge", r"marked", r"extensive", r"massive",            # en
              r"moderad", r"importante", r"abundante", r"cuantios",                    # es
              r"\borta\b", r"belirgin", r"fazla",                                      # tr
              r"umjeren", r"\bvec", r"obiln", r"izrazen",                              # hr
              r"μετρι", r"μεγαλ", r"σημαντικ",                                         # el
              r"ausgepragt", r"deutlich", r"massiv", r"\bgross", r"erheblich",         # de
              r"\bmatig", r"\bgroot", r"uitgesproken",                                 # nl
              r"modere", r"abondant", r"important",                                    # fr
              r"умерен", r"голям", r"значител", r"изразен")                            # bg


def fuera_de_la_articulacion(o, m):
    """E2: ¿la mención m es líquido FUERA de la articulación (otra bursa, quiste, subcutáneo, ligamento)?
    Una bursa precedida por "suprapatelar" no excluye, aunque la ventana de ±40 caracteres corte la palabra
    ("suprapatellar | bursada ve diz eklemi içerisinde ... sıvı")."""
    ini, fin = max(0, m.start() - 40), m.end() + 40
    excluyen = [x for x in NO_ARTICULAR.finditer(o, ini, fin)
                if not (x.group().startswith(("burs", "burz")) and "suprapatel" in o[max(0, x.start() - 25):x.start()])]
    return bool(excluyen) and "suprapatel" not in o[ini:fin]


def clasificar_effusion(o):
    resultados = []
    for m in DERRAME.finditer(o):
        if fuera_de_la_articulacion(o, m):
            continue                                                          # E2
        if negado(o, m):                                                       # incluye E3 (tras ':')
            resultados.append((0, "negado"))
            continue
        cerca = o[max(0, m.start() - 30):m.start()] + " " + o[m.end():m.end() + 30].split(",")[0]
        if FISIOLOGICO.search(cerca):
            resultados.append((0, "fisiológico (E1)"))
        elif dudoso(o, m):
            resultados.append((-1, "incierto"))
        elif POCO.search(cerca) and not MUCHO.search(cerca):
            resultados.append((-1, "mínimo/pequeño (E1)"))
        else:
            resultados.append((1, "derrame"))
    return lo_mas_fuerte(resultados)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════
#  BAKER'S
#  B1. Cualquier tamaño cuenta (un quiste existe o no existe). Roto o con fuga -> 1.
#  B2. Quiste en la fosa poplítea aunque no diga "Baker" -> 1. Quiste parameniscal o ganglión NO es Baker's.
#  B3. Líquido en la bursa del semimembranoso SIN mencionar el gastrocnemio -> -1.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
QUISTE, POPLITEO = r"(cyst|cist|kist|kyst|zyst|κυστ|кист)", r"(poplit|ιγνυακ|поплит)"
BAKER = regex(r"baker", r"бейкер", r"бекер",
              QUISTE + r"\w*[^.]{0,40}" + POPLITEO,                                 # B2: "quiste ... poplíteo"
              POPLITEO + r"\w*[^.]{0,40}" + QUISTE,                                 # B2: "poplitealna cista"
              r"gastrocnem\w*[- ]semimembran", r"semimembran\w*[- ]gastrocnem")     # bursa del Baker's
BAKER_DUDOSO = regex(r"burz\w* semimembran", r"burs\w* semimembran", r"semimembran\w* burs")   # B3
NO_BAKER = regex(r"menisc", r"menisk", r"μηνισκ", r"мениск", r"gangli", r"γαγγλι")


def clasificador_hallazgo(mencion, excluir=None, mencion_dudosa=None):
    """Clasificador de oraciones para un hallazgo que "está o no está" (sin grados):
    mención negada -> 0, con duda -> -1, mención dudosa (p. ej. B3) -> -1, si no -> 1."""
    def clasificar(o):
        resultados = []
        for patron, valor in [(mencion, 1), (mencion_dudosa, -1)]:
            if patron is None:
                continue
            for m in patron.finditer(o):
                if excluir is not None and excluir.search(o[max(0, m.start() - 40):m.end() + 40]):
                    continue
                if negado(o, m):
                    resultados.append((0, "negado"))
                elif dudoso(o, m):
                    resultados.append((-1, "incierto"))
                else:
                    resultados.append((valor, "positivo" if valor == 1 else "mención dudosa"))
        return lo_mas_fuerte(resultados)
    return clasificar


clasificar_baker = clasificador_hallazgo(BAKER, excluir=NO_BAKER, mencion_dudosa=BAKER_DUDOSO)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════
#  CONTUSION y FRACTURE (las dos se ven como edema óseo en la RM)
#  C1.  "Contusión" / "bone bruise" / "postkontuzijski" / "контузионен" dicho explícitamente -> 1.
#  C1b. Edema óseo en contexto TRAUMÁTICO ("postraumático", luxación, "pivot shift", "kissing") -> 1.
#  C2.  Edema óseo en contexto DEGENERATIVO o REACTIVO (condropatía, artrosis, osteofitos, fragmento meniscal,
#       osteonecrosis, insuficiencia) -> 0.
#  C3.  Edema óseo SIN contexto -> -1.
#  C4.  Edema óseo ASOCIADO A UNA FRACTURA -> -1 en Contusion (misma lógica que C3).
#  F1.  Cualquier fractura cuenta -> 1 (subcortical, osteocondral, impactación, estrés/insuficiencia, Segond).
#       La AVULSIÓN solo cuenta si se habla de hueso o fragmento; la avulsión de un ligamento no es fractura.
#  F2.  Fractura ANTIGUA o consolidada ("old", "healed", "alte", "stari", "ancienne"...) -> -1 (en toda la oración).
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
CONTUSION = regex(r"contusi", r"bruis", r"kontuz", r"θλασ", r"μωλωπ", r"kneuz", r"контузи")
_OSEO = r"(bone|marrow|medula|\bose[ao]|kemik|iligi|\bkost|srz|οστ|οστεομυελ|knochen|\bbot|osseu|костн)"
_EDEMA = r"(edem|oedem|odem|οιδημ|едем|оток)"
TRAUMATICO = regex(r"traumat", r"travmat", r"τραυματ", r"травмат", r"dislocat", r"luxat", r"luksac",
                   r"pivot", r"kissing", r"impact")                                    # C1b
EDEMA_OSEO = regex(_OSEO + r"\w*[^.]{0,25}" + _EDEMA, _EDEMA + r"\w*[^.]{0,25}" + _OSEO,
                   r"botoedeem", r"knochenmarkodem")
DEGENERATIVO = regex(r"condro", r"chondr", r"hondr", r"kondr", r"χονδρ", r"хондр", r"kraakbeen", r"knorpel",
                     r"cartilag", r"cartilla", r"kikirdak", r"k[iı]k[iı]rdak", r"hrskavic", r"хрущял",
                     r"osteoart", r"artros", r"arthros", r"artroz", r"gonartr", r"αρθρωσ", r"артроз", r"\boa\b",
                     r"osteofit", r"osteophyt", r"οστεοφυτ", r"остеофит",
                     r"reacti", r"reakti", r"reactiv", r"αντιδραστ", r"реактив",
                     r"degenera", r"dejenera", r"degenerat", r"εκφυλισ", r"дегенера",
                     r"menisc", r"menisk", r"μηνισκ", r"мениск",
                     r"osteonecros", r"osteonekro", r"insufficien", r"insuficien", r"stress")
FRACTURA = regex(r"fractur", r"\bfx\b", r"k[iı]r[iı]k", r"fraktur", r"prijelom", r"καταγμ", r"\bbruch",
                 r"fractuur", r"\bbreuk", r"фрактур", r"счупван", r"segond",
                 r"avul[sz]\w*[^.]{0,25}(fragment|fractur|fraktur|bony|osseous|\bkost|knoch|osseu|костн|οστ)",   # F1
                 r"(fragment|bony|osseous|\bkost|knoch|костн|οστ)\w*[^.]{0,25}avul[sz]", r"avulsionsfragment")
ANTIGUA = regex(r"\bold\b", r"healed", r"consolidat", r"\balte", r"\beski\b", r"\bstar[iaoe]\b",
                r"παλαι", r"\boude?\b", r"ancien", r"\bстар", r"postoperat", r"osteosynth",
                r"remov", r"resorb", r"surg", r"previous")      # fragmentos extirpados o de una cirugía previa


def clasificar_contusion(o):
    resultados = []
    for m in CONTUSION.finditer(o):                                   # C1
        if negado(o, m):
            resultados.append((0, "negado"))
        elif dudoso(o, m):
            resultados.append((-1, "incierto"))
        else:
            resultados.append((1, "contusión (C1)"))
    for m in EDEMA_OSEO.finditer(o):
        if negado(o, m):
            resultados.append((0, "negado"))
        elif TRAUMATICO.search(o):
            resultados.append((1, "edema traumático (C1b)"))
        elif DEGENERATIVO.search(o):
            resultados.append((0, "edema reactivo/degenerativo (C2)"))
        else:
            resultados.append((-1, "edema sin contexto (C3)"))
    return lo_mas_fuerte(resultados)


def clasificar_fractura(o):
    resultados = []
    for m in FRACTURA.finditer(o):
        if negado(o, m):
            resultados.append((0, "negado"))
        elif dudoso(o, m):
            resultados.append((-1, "incierto"))
        elif ANTIGUA.search(o):                                     # F2: en toda la oración
            resultados.append((-1, "antigua (F2)"))
        else:
            resultados.append((1, "fractura (F1)"))
    return lo_mas_fuerte(resultados)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════
#  MENISCOS (Medial Meniscus y Lateral Meniscus): rotura, grado y LADO
#  M1. Cualquier ROTURA cuenta -> 1 (parcial, degenerativa, radial, horizontal, compleja, asa de cubo, raíz, ramp, colgajo).
#  M2. Degeneración, meniscopatía, degeneración mucoide o señal de grado I-II SIN rotura -> 0.
#  M3. Señal de grado III/IV -> 1.  M3b. La señal "llega a la superficie articular" -> 1.
#  M4. Cambios postquirúrgicos (meniscectomía), extrusión, o "lesión" sin grado ni rotura -> -1.
#  M5. LADO por mención (antes, después, en la palabra "Innenmeniskus" o en grupo -> los dos). Sin lado se usa el
#      de la última mención con lado del reporte; si tampoco hay: negación -> los dos; rotura -> -1 en los dos.
#      Cada palabra de estado se asigna a la mención MÁS CERCANA.
#  M6. No son el menisco: ligamento menisco-femoral/tibial, quiste para/perimeniscal, receso meniscal.
#  M7. Un grado precedido por una escala o palabra de CARTÍLAGO ("ICRS grade III") es del cartílago -> se ignora.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
MENISCO = regex(r"\w*(menisc|menisk|menisq|μηνισκ|мениск)\w*")
NO_MENISCO = regex(r"femoral", r"tibial", r"kapsul", r"capsul", r"^peri", r"^para", r"recess")      # M6 (dentro de la palabra)
LADO_MED = regex(r"\bmedia\w*", r"\bmedij\w*", r"\bmedya\w*", r"\bintern[oae]\b", r"\binternal\b", r"\bεσω\b", r"\binnen",
                 r"\bmediaal\b", r"\bмедиал\w*")
LADO_LAT = regex(r"\blatera\w*", r"\bextern[oae]\b", r"\bexternal\b", r"\bεξω\b", r"\bau(ss|ß)en", r"\bлатерал\w*")
AMBOS = regex(r"menisci\b", r"meniscos\b", r"menisken\b", r"meniski\b", r"μηνισκοι", r"μηνισκων", r"menisques\b",
              r"meniscussen\b", r"менискуси", r"\bboth\b", r"\bambos\b", r"\bbeide\b", r"\boba\b", r"двата", r"\bdeux\b")
ROTURA_MEN = regex(ROTURA.pattern, r"\bramp\b", r"bucket", r"asa de cubo", r"\bflap\b", r"korb", r"emmerhengsel")
GRADO_ALTO = regex(r"(grade|grado|\bgrad|stupnj\w*|stupanj|βαθμ\w*|степен)\W{0,3}(iii|iv|3|4)\b", r"\b(iii|iv)°",
                   r"(extend|reach)\w* (in)?to the (articular )?surface",                                  # M3b
                   r"llega\w* a la superficie", r"atteint la surface", r"eklem yuzey\w* ulas",
                   r"doseze do (zglobne|artikul)", r"достига до (ставния|артикулиращия)")
GRADO_BAJO = regex(r"(grade|grado|\bgrad|stupnj\w*|stupanj|βαθμ\w*|степен)\W{0,3}(i|ii|1|2)[ab]?\b", r"\b(i|ii)°",
                   r"[–-]\s*2[аa]\b")                                                          # bg "– 2а"
GRADO_CARTILAGO = regex(r"icrs", r"outerbridge", r"chondr", r"χονδρ", r"kondr", r"hondr", r"k[iı]k[iı]rdak",
                        r"cartilag", r"хрущял", r"kraakbeen", r"knorpel")                     # M7
DEGEN_MEN = regex(r"degenera", r"dejenera", r"εκφυλισ", r"дегенера", r"meniskopati", r"meniscopat", r"mucoid",
                  r"mukoid", r"myxoid", r"miksoid", r"intrasubstance")
DUDOSO_MEN = regex(r"postquir", r"post-?surg", r"postoperat", r"menisc?ectom", r"menisektom", r"meniskektom",
                   r"resect", r"operiert", r"extru", r"ekstruz", r"\blesion", r"\blezij", r"лезия", r"\bletsel",
                   r"lasion", r"увреда")


def lados(o, m, lado_previo=None):
    """M5: lados ({'M'}, {'L'} o los dos) de la mención m; si no tiene, el de la oración anterior (o None)."""
    antes = re.split(r"[,;:.]", o[max(0, m.start() - 45):m.start()])[-1]
    antes = " ".join(antes.split()[-4:])                                   # hasta 4 palabras antes
    despues = re.split(r"[,;:.]", o[m.end():m.end() + 20])[0].split()[:1]  # 1 palabra después
    zona = f"{antes} {m.group()} {' '.join(despues)}"
    resultado = ({"M"} if LADO_MED.search(zona) else set()) | ({"L"} if LADO_LAT.search(zona) else set())
    if not resultado and AMBOS.search(zona):
        resultado = {"M", "L"}
    if not resultado:                                                       # "in the medial compartment, the meniscus..."
        previos = [(x.start(), "M") for x in LADO_MED.finditer(o[:m.start()])] + \
                  [(x.start(), "L") for x in LADO_LAT.finditer(o[:m.start()])]
        if previos:
            resultado = {max(previos)[1]}
    return resultado or lado_previo


def ultimo_lado(o, lado_previo=None):
    """Lado (uno solo) de la última mención del menisco en la oración; sirve de contexto para la siguiente."""
    for m in reversed(list(MENISCO.finditer(o))):
        l = lados(o, m)
        if l is not None and len(l) == 1:
            return l
    return lado_previo


def clasificar_meniscos(o, lado_previo=None):
    """Devuelve {'M': (etiqueta, motivo), 'L': (...)} para UNA oración, o None si no habla de los meniscos."""
    menciones = [m for m in MENISCO.finditer(o) if not NO_MENISCO.search(m.group())]
    if not menciones:
        return None
    estados = {i: [] for i in range(len(menciones))}
    for tipo, patron in [("rotura", ROTURA_MEN), ("alto", GRADO_ALTO), ("bajo", GRADO_BAJO),
                         ("degen", DEGEN_MEN), ("dudoso", DUDOSO_MEN), ("normal", NORMAL)]:
        for s in patron.finditer(o):
            if any(s.start() < m.end() and m.start() < s.end() for m in menciones) and tipo != "dudoso":
                continue                                    # la palabra de estado está DENTRO de la mención
            if tipo in ("alto", "bajo") and GRADO_CARTILAGO.search(o[max(0, s.start() - 15):s.start()]):
                continue                                    # M7: el grado es del cartílago
            dist = [max(m.start() - s.end(), s.start() - m.end(), 0) for m in menciones]
            estados[dist.index(min(dist))].append((tipo, s))
    salida = {}
    for i, m in enumerate(menciones):
        tipos = {t for t, _ in estados[i]}
        roturas = [s for t, s in estados[i] if t == "rotura"]
        if roturas and not all(negado(o, s) for s in roturas):
            s = next(s for s in roturas if not negado(o, s))
            res = (-1, "rotura incierta") if dudoso(o, s) else (1, "rotura (M1)")
        elif any(t == "alto" and not negado(o, s) for t, s in estados[i]):   # "without ... extending into the surface"
            res = (1, "grado III-IV (M3)")
        elif roturas:
            res = (0, "rotura negada")
        elif "bajo" in tipos or "degen" in tipos:
            res = (0, "degeneración / grado I-II (M2)")
        elif "dudoso" in tipos:
            res = (-1, "postquirúrgico / extrusión / lesión (M4)")
        elif "normal" in tipos:
            res = (0, "normal")
        else:
            continue
        lado = lados(o, m, lado_previo)
        if lado is None:                                    # M5: sin lado
            if res[0] == 1:
                res, lado = (-1, "rotura sin lado (M5)"), {"M", "L"}
            elif res[0] == 0:
                lado = {"M", "L"}
            else:
                continue
        for l in lado:
            previo = salida.get(l)
            if previo is None or ORDEN[res[0]] > ORDEN[previo[0]]:
                salida[l] = res
    return salida or None


# ══════════════════════════════════════════════════════════════════════════════════════════════════════
#  ARTROSIS (Medial OA, Lateral OA, PF OA)
#  A1. Artrosis NOMBRADA en un compartimento -> 1, aunque sea incipiente o leve.
#  A2. OSTEOFITOS en un compartimento -> 1.
#  A3. Cartílago de ALTO grado SIN palabra de artrosis ni osteofitos -> -1. Daño de cartílago SIN grado -> -1.
#  A4. Cartílago de BAJO grado (I-II, superficial, leve, fibrilación) o normal -> 0.
#  A5. Solo estrechamiento del espacio articular -> -1.
#  A6. Compartimentos M, L y PF (la "faceta medial de la rótula" es PF). "Tricompartimental" -> los tres.
#      Femorotibial sin lado -> M y L. Artrosis SIN compartimento ("gonartrosis") -> -1 en los tres.
#      El compartimento se arrastra de la oración anterior.
#  A7. Lo dicho del menisco, ligamentos, tendones o músculos NO es artrosis. "Subcondral"/"osteocondral" no es cartílago.
#  A8. Una palabra de daño NEGADA no cuenta. Un lado unido por "y/and/und..." a una mención PF vale también.
#  A9. Artrosis nombrada y osteofitos valen para TODOS los compartimentos de su oración; si no nombra ninguno se
#      arrastra el anterior, SALVO que hable de toda la rodilla (-> A6). "Lateral/medial" pegado a "patelofemoral"
#      es una faceta de la rótula -> PF. Hemartrosis, lipohemartrosis e hidrartrosis NO son artrosis.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
ANATOMIA = regex(r"\w*compart\w*", r"\w*kompart\w*", r"διαμερισμ\w*", r"компартимент\w*", r"condyl\w*", r"condil\w*",
                 r"kondil\w*", r"kondyl\w*", r"κονδυλ\w*", r"кондил\w*", r"plateau\w*", r"platillo\w*", r"\bplato\w*",
                 r"πλατω", r"плато", r"tibi\w*femor\w*", r"femor\w*tibi\w*", r"κνημομηριαι\w*", r"\bfemur\w*",
                 r"\btibia\w*", r"фемур\w*", r"тибия\w*")
PATELOFEMORAL = regex(r"\w*patel\w*", r"\w*rotul\w*", r"trochle\w*", r"troclea\w*", r"trohle\w*", r"troklea\w*",
                      r"trchlear", r"επιγονατιδ\w*", r"τροχιλ\w*", r"пател\w*", r"трохле\w*", r"\bpf\b")
TRES = regex(r"tri-?compart\w*", r"tri-?kompart\w*", r"all three", r"three compartments", r"tres compartimentos",
             r"τριων διαμερισματων", r"alle drei", r"drie compartiment", r"trois compartiments", r"три компартимента",
             r"uc kompartman", r"sva tri")
NO_COMPARTIMENTO = regex(r"tendon", r"tendin", r"\bpees", r"sehne", r"tetiv", r"τενοντ", r"сухожил", r"ligam",
                         r"retinac", r"retinak", r"bursa", r"tuberos", r"\bpol\b", r"\bpole\b", r"kemik")
SUMIDERO = regex(MENISCO.pattern, LCA_SOLO.pattern, CRUZADOS.pattern, r"\w*ligam\w*", r"\w*collateral\w*",
                 r"\w*kolat\w*", r"\w*kollat\w*", r"\w*tendon\w*", r"\w*tendin\w*", r"\w*sehne\w*", r"\w*tetiv\w*",
                 r"συνδεσμ\w*", r"лигамент\w*", r"\bmcl\b", r"\blcl\b", r"\bmpfl\b",
                 r"\w*muscul\w*", r"\w*muskul\w*", r"gastro\w*", r"\binsert\w*", r"hvatist\w*", r"enthes\w*",
                 r"μυ[οϊ]\w*", r"мускул\w*")                                                  # A7
RODILLA = regex(r"\bknee\b", r"rodilla", r"\bknie", r"kniegelenk", r"\bdiz\b", r"koljen", r"γονατ", r"колян", r"genou")
NO_ES_ARTROSIS = regex(r"^(lipo)?h(a)?em", r"^hidr", r"^hydr", r"^υδ", r"^αιμ", r"^хем", r"^хидр")   # A9
OA_PALABRA = regex(r"osteoar", r"\boa\b", r"arthros", r"artros", r"artroz", r"gonart", r"gonarth", r"dejeneratif artrit",
                   r"degenerative joint", r"\bdjd\b", r"οστεοαρθρ", r"αρθροπαθ", r"артроз",
                   r"degenerati\w* (change|cambio|verander|promjen|changement|veranderung)", r"cambios degenerativos",
                   r"changements degeneratifs", r"εκφυλιστικ\w* αλλοιωσ", r"дегенеративни промени", r"dejeneratif degisik")
OSTEOFITO = regex(r"osteophyt", r"osteofit", r"οστεοφυτ", r"остеофит", r"osteofyt")
ESPACIO = regex(r"joint space narrow", r"narrowing of the joint space", r"estrechamiento del espacio", r"pincement",
                r"στενωση του μεσαρθρ", r"стеснение на ставната", r"gelenkspaltverschmal", r"eklem aral\w* daralma",
                r"suzenje zglobn", r"gewrichtsspleetversmall")
CARTILAGO = regex(r"\w*chondr\w*", r"\w*condr\w*", r"\w*kondr\w*", r"\w*hondr\w*", r"\w*χονδρ\w*", r"\w*хондр\w*",
                  r"cartilag\w*", r"cartila\w*", r"k[iı]k[iı]rdak\w*", r"hrskav\w*", r"\w*knorpel\w*", r"kraakbeen\w*",
                  r"хрущял\w*")
NO_CARTILAGO = regex(r"subchondr", r"subcondr", r"subkondr", r"subhondr", r"osteochondr", r"osteocondr",
                     r"osteokondr", r"osteohondr", r"οστεοχονδρ", r"υποχονδρ", r"остеохондр", r"субхондр")
DANO_CART = regex(r"malac", r"malaz", r"pat(h)?i", r"\bosis", r"chondrosis", r"defect", r"defekt", r"\bloss", r"perdida",
                  r"verlies", r"lijden", r"kayb", r"incel", r"thinn", r"adelgaz", r"λεπτυνσ", r"διαβρωσ", r"erosi",
                  r"ulcer", r"fissur", r"fisur", r"denud", r"fraying", r"fibril", r"wear", r"irregular", r"изтън",
                  r"дефект", r"damage", r"schaden", r"verdun", r"attenuation", r"εξαλειψ", r"απωλει", r"πατεια")
CART_ALTO = regex(GRADO_ALTO.pattern, r"full[- ]thickness", r"espesor total", r"ολικου (παχους|βαθους)", r"volledig",
                  r"complete (cartilage )?loss", r"denud", r"high[- ]grade", r"expos", r"πληρης εξαλειψη", r"tam kat",
                  r"butunluk kayb", r"pleine epaisseur", r"sever", r"gevorderd", r"uznapredoval", r"advanced",
                  r"avanzad", r"ileri derece", r"\[grade 4\]")
CART_BAJO = regex(GRADO_BAJO.pattern, r"low[- ]grade", r"superficial", r"oberflach", r"fibrilla", r"fraying", r"\bmild",
                  r"\bleve\b", r"\blegere?\b", r"lichtgradig", r"hafif", r"\bblag", r"discret", r"gering", r"\bηπι",
                  r"слабо", r"less than 50", r"<\s*50", r"\bminim", r"\bfocal")
_LADO_CONJ = (r"(media\w*|medij\w*|medya\w*|latera\w*|intern[oae]|extern[oae]|εσω|εξω)"
              r"\s*(and|y|e|i|und|en|et|ve|και|и|,)\s*$")                                  # A8: "medial and patellofemoral"


def _lado_unido(o, m):
    """A8: lado unido por una conjunción justo antes de una mención PF."""
    lado = o[max(0, m.start() - 30):m.start()]
    if not re.search(_LADO_CONJ, lado):
        return set()
    return ({"M"} if LADO_MED.search(lado) else set()) | ({"L"} if LADO_LAT.search(lado) else set())


def compartimentos(o, m, previo=None):
    """A6: compartimentos ({'M','L','PF'}) de una mención anatómica, o el de la oración anterior (o None)."""
    if TRES.search(m.group()):
        return {"M", "L", "PF"}
    antes = " ".join(re.split(r"[,;:.]", o[max(0, m.start() - 45):m.start()])[-1].split()[-4:])
    despues = " ".join(re.split(r"[,;:.]", o[m.end():m.end() + 25])[0].split()[:2])
    zona = f"{antes} {m.group()} {despues}"
    if NO_COMPARTIMENTO.search(f"{m.group()} {despues}"):
        return None
    res = set()
    pegado = " ".join(antes.split()[-1:] + [m.group()] + despues.split()[:1])   # la mención y sus 2 vecinas
    if PATELOFEMORAL.search(pegado):
        return {"PF"} | _lado_unido(o, m)                   # A9: "lateralnog kompartmenta femoropatelarnog" -> PF
    if PATELOFEMORAL.search(zona):
        res = {"PF"} | _lado_unido(o, m)
    if not PATELOFEMORAL.search(m.group()):
        res |= ({"M"} if LADO_MED.search(zona) else set()) | ({"L"} if LADO_LAT.search(zona) else set())
        if not res and re.search(r"tibi\w*femor|femor\w*tibi|κνημομηριαι|femur|tibia|фемур|тибия", m.group()):
            res = {"M", "L"}                                               # femorotibial sin lado
    return res or previo


def clasificar_artrosis(o, previo=None):
    """Devuelve {'M'|'L'|'PF': (etiqueta, motivo)} para UNA oración, o None."""
    menciones = []                                                      # (inicio, fin, compartimentos | 'sumidero')
    for patron in (ANATOMIA, PATELOFEMORAL, TRES):
        for m in patron.finditer(o):
            comp = compartimentos(o, m)
            if comp:
                menciones.append((m.start(), m.end(), comp))
    for m in SUMIDERO.finditer(o):
        menciones.append((m.start(), m.end(), "sumidero"))
    eventos = []                                                        # (inicio, fin, etiqueta, motivo)
    for patron, etq, motivo in [(OA_PALABRA, 1, "artrosis nombrada (A1)"), (OSTEOFITO, 1, "osteofitos (A2)"),
                                (ESPACIO, -1, "solo espacio articular (A5)")]:
        for s in patron.finditer(o):
            if motivo.startswith("artrosis") and o[s.end():].lstrip().startswith(":"):
                continue                                                # "changements dégénératifs :" es un título
            palabra = re.findall(r"\w*$", o[:s.start()])[0] + o[s.start():s.end()]   # la palabra completa
            if NO_ES_ARTROSIS.search(palabra):
                continue                                                # A9: hemartrosis, hidrartrosis...
            if negado(o, s):
                eventos.append((s.start(), s.end(), 0, "negado"))
            elif dudoso(o, s):
                eventos.append((s.start(), s.end(), -1, "incierto"))
            else:
                eventos.append((s.start(), s.end(), etq, motivo))
    for c in CARTILAGO.finditer(o):
        if NO_CARTILAGO.search(c.group()):
            continue
        ini_cerca = max(0, c.start() - 40)
        cerca = o[ini_cerca:c.end() + 40]
        dano = [d for d in DANO_CART.finditer(o, ini_cerca, c.end() + 40) if not negado(o, d)]   # A8
        if negado(o, c) or (not dano and (NORMAL.search(cerca) or DANO_CART.search(cerca))):
            eventos.append((c.start(), c.end(), 0, "cartílago normal"))
        elif not dano:
            continue
        elif CART_ALTO.search(cerca):
            eventos.append((c.start(), c.end(), -1, "cartílago alto grado (A3)"))
        elif CART_BAJO.search(cerca):
            eventos.append((c.start(), c.end(), 0, "cartílago bajo grado (A4)"))
        else:
            eventos.append((c.start(), c.end(), -1, "cartílago sin grado (A3)"))
    salida = {}
    todos = set().union(*[c for _, _, c in menciones if c != "sumidero"])    # compartimentos de la oración
    for ini, fin, etq, motivo in eventos:
        if menciones:
            dist = [max(a - fin, ini - b, 0) for a, b, _ in menciones]
            comp = menciones[dist.index(min(dist))][2]
        else:
            comp = None
        if comp == "sumidero":
            continue                                                    # A7: habla del menisco/ligamento/músculo
        if motivo in ("artrosis nombrada (A1)", "osteofitos (A2)"):
            comp = todos or (None if RODILLA.search(o) else previo)     # A9
        elif comp is None:
            comp = previo
        if comp is None:                                                # A6: sin compartimento
            if etq == 1:
                etq, motivo, comp = -1, "artrosis sin compartimento (A6)", {"M", "L", "PF"}
            elif etq == 0:
                comp = {"M", "L", "PF"}
            else:
                continue
        for k in comp:
            if k not in salida or ORDEN[etq] > ORDEN[salida[k][0]]:
                salida[k] = (etq, motivo)
    return salida or None


def ultimo_compartimento(o, previo=None):
    ultimo = None
    for patron in (ANATOMIA, PATELOFEMORAL, TRES):
        for m in patron.finditer(o):
            comp = compartimentos(o, m)
            if comp and (ultimo is None or m.start() > ultimo[0]):
                ultimo = (m.start(), comp)
    return ultimo[1] if ultimo else previo


# ══════════════════════════════════════════════════════════════════════════════════════════════════════
#  MCL y SYNOVITIS
#  K1. Rotura del MCL (parcial o completa) -> 1, igual que el LCA (L1).
#  K2. Esguince/lesión de grado II-III, "high-grade" o moderado/severo -> 1.
#  K3. Esguince/lesión de grado I, "low-grade", edema periligamentario, engrosamiento o lesión antigua -> -1.
#  K4. El MCL también se nombra en grupo (exige PLURAL). Las palabras de estado se asignan a la estructura MÁS
#      CERCANA (LCA, LCL, menisco, tendón... son sumideros). Si dos menciones se solapan gana la que empieza antes.
#  K5. "Pérdida (parcial) de continuidad" / "bütünlük kaybı" / "devamsızlık" = rotura -> 1.
#      Duda turca pospuesta "olabilecek/olabilir" -> -1 (ver INCIERTO_DESPUES).
#  S1. Sinovitis nombrada, o engrosamiento/hipertrofia/proliferación sinovial -> 1.
#  S2. NO son sinovitis: plica, condromatosis sinovial, quiste/evaginación sinovial, Hoffa, lipoma arborescens.
#  S3. Sinovitis villonodular pigmentada (PVNS) -> -1.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
MCL_SOLO = regex(r"\bmcl\b", r"medial collateral", r"tibial collateral", r"colateral (medial|interno)", r"\blcm\b",
                 r"\blli\b", r"lateral interno", r"med[iy]al kollateral", r"medij\w* kolateral\w*", r"εσω πλαγι\w*",
                 r"innenband", r"medial\w* (und lateral\w* )?(kollateral|seiten)band", r"mediaa?le? collatera\w*",
                 r"binnenband", r"collateral\w* (medial|interne)", r"медиал\w* колатерал\w*")
COLATERALES = regex(r"collateral ligaments", r"colaterales\b", r"kollateral ligamanlar", r"kolateralni ligamenti",
                    r"kolateralnih ligamenata",
                    r"πλαγιοι συνδεσμοι", r"πλαγιων συνδεσμων", r"kollateralband(er|apparat)", r"collaterale banden",
                    r"laterale banden", r"ligaments collateraux", r"колатерални\w* лигамент\w*",
                    r"lateral ve medial kollateral")
OTRAS_ESTRUCTURAS = regex(LCA_SOLO.pattern, r"\bpcl\b", r"posterior cruciate", r"cruzado posterior", r"arka capraz",
                          r"straznj\w* kriz", r"οπισθι\w* χιαστ", r"hinter\w* kreuzband", r"achterste kruisband",
                          r"croise posterieur", r"задн\w* кръстн", r"\blcl\b", r"lateral collateral",
                          r"colateral (lateral|externo)", r"lateral\w* kolateral", r"lateral kollateral", r"εξω πλαγι",
                          r"au(ss|ß)enband", r"lateral\w* kollateralband", r"латерал\w* колатерал", r"\bmpfl\b",
                          MENISCO.pattern, r"\w*tendon\w*", r"\w*tendin\w*", r"\w*sehne\w*", r"\w*tetiv\w*", r"\bpees\b",
                          r"retinac\w*", r"retinak\w*",
                          CARTILAGO.pattern)        # "...(grade 1 sprain).patellar kıkırdak ... bütünlük kaybı" es del cartílago
LESION_LIG = regex(LESION.pattern, r"\bsprain", r"\bburkul", r"\bistegin", r"kalınlas", r"kalinlas", r"thicken",
                   r"engrosamiento", r"zadeb", r"πα[χ]υνσ", r"verdick", r"verdikking", r"epaississ", r"задебел",
                   r"periligament", r"pellegrini", r"\bodem", r"reizzustand", r"\bold\b", r"chronic", r"cronic", r"kronik")
LESION_ALTA = regex(r"(grade|grado|\bgrad|stupnj\w*|stupanj|βαθμ\w*|степен)\W{0,3}(ii|iii|2|3)\b", r"\b(ii|iii)°",
                    r"high[- ]grade", r"moderat", r"moderad", r"sever", r"\bvisok", r"hochgradig")
ROTURA_LIG = regex(ROTURA.pattern, r"perdida (parcial )?de (la )?continuidad", r"loss of (its )?continuity",
                   r"butunluk kayb", r"devams[iı]zl[iı]k", r"gubit\w* kontinuitet", r"perte de continuite",
                   r"загуба на (целостта|непрекъснатост)")                                         # K5


def clasificar_mcl(o):
    """Etiqueta del MCL en UNA oración (asignando cada palabra de estado a la estructura más cercana), o None."""
    objetivo = [m for p in (MCL_SOLO, COLATERALES) for m in p.finditer(o)]
    otras = list(OTRAS_ESTRUCTURAS.finditer(o))
    solapan = lambda a, b: a.start() < b.end() and b.start() < a.end()
    # K4: si una mención del MCL y otra estructura se solapan, gana la que empieza antes
    objetivo = [t for t in objetivo if not any(solapan(t, m) and m.start() < t.start() for m in otras)]
    otras = [m for m in otras if not any(solapan(t, m) and t.start() <= m.start() for t in objetivo)]
    if not objetivo:
        return None
    menciones = [(m, True) for m in objetivo] + [(m, False) for m in otras]
    resultados = []
    for tipo, patron in [("rotura", ROTURA_LIG), ("lesion", LESION_LIG), ("normal", NORMAL)]:
        for s in patron.finditer(o):
            dist = [max(m.start() - s.end(), s.start() - m.end(), 0) for m, _ in menciones]
            if not menciones[dist.index(min(dist))][1]:
                continue                                                 # K4: es de otra estructura
            cerca = o[max(0, s.start() - 30):s.end() + 30]
            if tipo == "normal":
                resultados.append((0, "normal"))
            elif negado(o, s):
                resultados.append((0, "negado"))
            elif dudoso(o, s):
                resultados.append((-1, "incierto"))
            elif tipo == "rotura":
                resultados.append((1, "rotura (K1)"))
            elif LESION_ALTA.search(cerca):
                resultados.append((1, "esguince grado II-III (K2)"))
            else:
                resultados.append((-1, "esguince grado I / edema / antiguo (K3)"))
    return lo_mas_fuerte(resultados)


SINOVITIS = regex(r"synovit", r"sinovit", r"synovialit", r"synoviit", r"υμενιτ", r"синовит",
                  r"(synovial|sinovial|sinovyal|sinovijal\w*|synoviale?|синовиал\w*) (thicken|hypertroph|prolifer|engros"
                  r"|kalınlas|kalinlas|zadeb|hipertrof|verdick|verdikking|epaiss|задебел|хипертроф)\w*",
                  r"(hypertrophy|thickening|proliferation) of the synovium", r"υμενικ\w* (παχυνσ|υπερτροφ)\w*")
NO_SINOVITIS = regex(r"plica", r"plika", r"plik", r"πτυχ", r"chondromatos", r"kondromatoz", r"hondromatoz",
                     r"aussackung", r"lipoma", r"arboresc", r"hoffa")                         # S2
PVNS = regex(r"villonodul", r"\bpvns\b", r"βιλλοοζωδ", r"вилонодул")                         # S3


def clasificar_sinovitis(o):
    resultados = []
    for m in SINOVITIS.finditer(o):
        if NO_SINOVITIS.search(o[m.start():m.end() + 25]):
            continue                                                     # S2: "sinovyal plika", etc.
        if negado(o, m):
            resultados.append((0, "negado"))
        elif PVNS.search(o[max(0, m.start() - 40):m.end() + 10]):
            resultados.append((-1, "PVNS (S3)"))
        elif dudoso(o, m):
            resultados.append((-1, "incierto"))
        else:
            resultados.append((1, "sinovitis (S1)"))
    return lo_mas_fuerte(resultados)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════
#  EXTRACTOR FINAL
# ══════════════════════════════════════════════════════════════════════════════════════════════════════
# Clasificadores de UNA oración -> (etiqueta, motivo) o None
CLASIFICADORES = {"ACL": clasificar_lca, "MCL": clasificar_mcl, "Effusion": clasificar_effusion,
                  "Synovitis": clasificar_sinovitis, "Baker's": clasificar_baker,
                  "Contusion": clasificar_contusion, "Fracture": clasificar_fractura}
MENISCOS = {"M": "Medial Meniscus", "L": "Lateral Meniscus"}
ARTROSIS = {"M": "Medial OA", "L": "Lateral OA", "PF": "PF OA"}


def extraer_etiquetas(reporte_norm):
    """Reporte (ya normalizado: NFKC + limpiar_extra) -> {etiqueta: 1 / 0 / -1} para las 12 etiquetas (D1, D2)."""
    porta = {k: [] for k in LABELS}
    lado_previo = comp_previo = None
    for o in oraciones(para_buscar(reporte_norm)):                             # D4, D3
        if es_antecedente(o):                                                  # D6
            continue
        for etiqueta, clasificar in CLASIFICADORES.items():
            res = clasificar(o)
            if res is not None:
                porta[etiqueta].append(res[0])
        for lado, (etq, _) in (clasificar_meniscos(o, lado_previo) or {}).items():
            porta[MENISCOS[lado]].append(etq)
        for comp, (etq, _) in (clasificar_artrosis(o, comp_previo) or {}).items():
            porta[ARTROSIS[comp]].append(etq)
        lado_previo = ultimo_lado(o, lado_previo)
        comp_previo = ultimo_compartimento(o, comp_previo)
    return {k: etiqueta_estudio(v) for k, v in porta.items()}                 # sin menciones -> 0 (D2)
