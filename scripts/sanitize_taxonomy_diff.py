#!/usr/bin/env python3
"""
sanitize_taxonomy_diff.py - Gate finale prima dell'export sul skills-repo.

Post-processing su taxonomy_diff.json: applica la anonymization_map propagata
da map_to_taxonomy, poi scarta le entries che dopo anonimizzazione:

  1) hanno un label con troppo poco contenuto significativo (< N caratteri
     alfanumerici, esclusi placeholder [X_N]) — es. "LAN [AZIENDA_1] [IP_1]
     (server)" diventa "LAN  (server)" -> troppo scarno per una pagina
     pubblica;

  2) contengono ANCORA pattern residui riconoscibili come sensibili (IP
     dotted-quad, email, hostname stile WIN*/USG*/NAS*/SRV*/VM<num>, domini
     di terzi fuori allowlist) che la mappa non ha catturato (one-off, casi
     di parsing anomali, categorie che la mappa non modella). Si scarta
     invece di lasciar passare — piu' sicuro perdere qualche entry marginale
     che pubblicare un IP interno.

Non modifica il file .md di diff (che resta strumento di revisione manuale
in chiaro): agisce solo sul JSON che finisce a export_to_taxonomy.

Uso:
  python scripts/sanitize_taxonomy_diff.py \\
    --input  _intermediate/taxonomy_diff.json \\
    --output _intermediate/taxonomy_diff.sanitized.json
"""

import argparse
import json
import re
import sys
from pathlib import Path


PLACEHOLDER_RE = re.compile(
    r"\[(?:AZIENDA|PERSONA|EMAIL|IP|HOSTNAME)_\d+\]"
)

# ---------------------------------------------------------------------------
# Fornitori: il nome passa, il sottodominio no
# ---------------------------------------------------------------------------
# I domini dei provider di hosting, registrazione e connettivita' con cui si
# lavora. Il dominio nudo e' permesso, perche' e' l'equivalente del nome del
# fornitore ed e' dichiarato a mano nelle sezioni delle tecnologie delle pagine
# pubbliche; qualunque sottodominio e' bloccato, perche' identifica una macchina
# o un tenant specifico e da un solo nome host si ricostruisce l'infrastruttura
# interna. I casi che hanno motivato la regola sono `cloudbackup.seeweb.it`,
# `fs20608.seewebcloud.it` e `regulus.fastnet.it`, comparsi nei preview del
# ciclo ARCHITETTURA.
PROVIDER_DOMAINS = (
    "seeweb.it", "seewebcloud.it", "fastnet.it", "aruba.it", "arubabusiness.it",
    "vianova.it", "register.it", "ovh.it", "ionos.it",
)

PROVIDER_SUBDOMAIN_RE = re.compile(
    r"\b[a-z0-9][a-z0-9\-]*\.(?:" +
    "|".join(re.escape(d) for d in PROVIDER_DOMAINS) +
    r")\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Domini di terzi
# ---------------------------------------------------------------------------
# La anonymization_map di enrich_graph non ha una categoria per i nomi di
# dominio: registra COMPANY, PROPER_NOUN, EMAIL, IP_ADDR e HOSTNAME, e nessuna
# delle tre regex che potrebbero pescare un dominio lo fa davvero. EMAIL_RE
# vuole la chiocciola, HOSTNAME_PREFIX_RE vuole un prefisso infrastrutturale
# tipo WIN o SRV, HOSTNAME_DASHED_RE vuole maiuscolo con trattino. La categoria
# URL viene estratta ma non entra nella mappa. Il risultato e' che un dominio
# nudo di un'azienda terza, per esempio quello comparso come nodo "Dominio
# sabaerospace.com", attraversa indenne tutti gli strati: non e' stato
# pubblicato solo perche' la classificazione gli ha dato punteggio zero, non
# perche' un gate lo abbia fermato. Questa regola chiude il buco a valle,
# dove passa tutto il testo destinato al repo pubblico.
#
# L'allowlist elenca i domini che su una pagina pubblica di tassonomia sono
# legittimi e attesi, e viene confrontata per suffisso, cosi' che un
# sottodominio di un dominio permesso resti permesso (docs.microsoft.com,
# alesop95.github.io, che e' poi il dominio delle pagine pubblicate). Contiene
# tre famiglie: i fornitori e i prodotti tecnologici citati come tecnologia, le
# fonti normative e istituzionali che i documenti di compliance citano per
# nome, e i namespace di codice che hanno la forma sintattica di un dominio
# (System.Net, java.io, ASP.NET) e che senza eccezione esplicita verrebbero
# scambiati per domini di terzi.
THIRD_PARTY_DOMAIN_ALLOWLIST = (
    # Fornitori e prodotti tecnologici
    "microsoft.com", "microsoftonline.com", "office.com", "office365.com",
    "azure.com", "windows.com", "live.com", "sharepoint.com",
    "google.com", "gmail.com", "googleapis.com", "youtube.com",
    "apple.com", "amazon.com", "amazonaws.com", "cloudflare.com",
    "github.com", "github.io", "gitlab.com", "bitbucket.org",
    "atlassian.com", "atlassian.net", "stackoverflow.com", "wikipedia.org",
    "python.org", "pypi.org", "docker.com", "kubernetes.io",
    # Documentazione tecnica e CDN citate nelle pagine e nei report: emerse dal
    # verificatore sull'albero di lavoro, sono fonti pubbliche e non terzi.
    "mkdocs.org", "dokuwiki.org", "ubuntu-it.org", "unpkg.com", "jsdelivr.net",
    "readthedocs.io", "readthedocs.org",
    "ubuntu.com", "canonical.com", "debian.org", "redhat.com", "suse.com",
    "kernel.org", "gnu.org", "apache.org", "mozilla.org", "letsencrypt.org",
    "vmware.com", "veeam.com", "acronis.com", "synology.com", "qnap.com",
    "zyxel.com", "fortinet.com", "sophos.com", "cisco.com", "ubnt.com",
    "eset.com", "kaspersky.com", "malwarebytes.com", "virustotal.com",
    "nvidia.com", "intel.com", "amd.com", "dell.com", "hp.com", "lenovo.com",
    "openai.com", "anthropic.com", "claude.ai", "obsidian.md",
    # Aggiunti dopo aver misurato la regola sui due corpora gia' lavorati,
    # endpoint e ARCHITETTURA: sono i soli falsi positivi che la misura ha
    # prodotto, e sono tutti prodotti documentati come tecnologia, quindi
    # bloccarli costava evidenze buone senza proteggere nulla. Le console
    # citate sono URL pubblici generici del vendor, non sottodomini che
    # identifichino il tenant. I provider di hosting restano invece esclusi
    # per scelta, insieme a Fastnet che ha gia' una regola sua: da un loro
    # sottodominio si ricostruisce l'infrastruttura interna.
    "bitdefender.com", "myzyxel.com", "supremocontrol.com",
    # Aggiunti dal ciclo Helpdesk RWS GroupShare Studio, misurando la regola sul
    # nuovo corpus: sono i portali del vendore del prodotto che l'intero corpus
    # documenta, cioe' gateway, appstore, community e docs, e bloccarli scrubava
    # i riferimenti alla fonte ufficiale della procedura.
    "rws.com", "sdl.com",
    # I domini nudi dei provider con cui si lavora: permessi qui perche' sono
    # dichiarati a mano nelle sezioni delle tecnologie, mentre i loro
    # sottodomini restano bloccati da PROVIDER_SUBDOMAIN_RE, che e' valutata a
    # parte e non ammette eccezioni per suffisso.
    *PROVIDER_DOMAINS,
    # Fonti normative e istituzionali
    "iso.org", "w3.org", "ietf.org", "rfc-editor.org", "nist.gov",
    "cisa.gov", "europa.eu", "garanteprivacy.it", "agid.gov.it", "acn.gov.it",
    # Namespace di codice con la forma di un dominio
    "asp.net", "vb.net", "ado.net", "system.net", "system.io",
    "java.io", "java.net", "microsoft.net",
)

# TLD noti accettati come terminazione di un dominio registrabile. La lista e'
# volutamente corta: ogni TLD in piu' allarga la superficie dei falsi positivi
# su testo tecnico, perche' un TLD di due lettere collide facilmente con una
# sigla o con una estensione di file. Sono ordinati per lunghezza decrescente
# per evitare che l'alternativa piu' corta vinca su quella piu' lunga (co
# prima di com).
KNOWN_TLDS = tuple(sorted(
    (
        "com", "it", "net", "org", "eu", "io", "dev", "app", "ai", "cloud",
        "info", "biz", "co", "gov", "edu", "tech",
        "de", "fr", "es", "uk", "ch", "at", "nl", "be", "us", "ca",
    ),
    key=len,
    reverse=True,
))

_DOMAIN_ALLOW_ALT = "|".join(re.escape(d) for d in THIRD_PARTY_DOMAIN_ALLOWLIST)
_DOMAIN_TLD_ALT = "|".join(KNOWN_TLDS)

# Il lookbehind impedisce di agganciare la coda di un dominio piu' lungo o la
# parte destra di un indirizzo email; il lookahead di allowlist assorbe gli
# eventuali sottodomini prima di confrontare il suffisso permesso.
THIRD_PARTY_DOMAIN_RE = re.compile(
    r"(?<![\w@.\-])"
    rf"(?!(?:[a-z0-9\-]+\.)*(?:{_DOMAIN_ALLOW_ALT})(?![\w\-]))"
    r"(?:[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?\.)+"
    rf"(?:{_DOMAIN_TLD_ALT})"
    r"(?![\w\-])",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Segreti
# ---------------------------------------------------------------------------
# Categoria a se', con un trattamento diverso da tutti gli altri residui: un
# segreto fa scartare l'evidenza sempre, anche quando compare nel preview, dove
# ogni altro residuo viene soltanto scrubato. La ragione e' che un residuo e' un
# dato scappato dentro un testo altrimenti utile, mentre una credenziale in
# chiaro dice che quel punto del documento e' un deposito di credenziali: il
# testo attorno non e' evidenza di competenza, e mascherare il valore lascerebbe
# pubblicato il resto della frase, cioe' a quale sistema e a quale utenza quella
# credenziale appartiene.
#
# Questa regola nasce dal ritrovamento peggiore della storia del progetto: tre
# password in chiaro pubblicate sul sito e presenti in tutti i commit, fra cui
# una di root su SSH. Nessuno strato le aveva viste. La mappa di anonimizzazione
# non le modella, perche' non sono entita' nominate; il gate non le cercava; e il
# filtro sui nomi di file di graphify, che avrebbe scartato un documento
# intitolato alle credenziali, guarda solo il nome e viene per di piu' aggirato
# di proposito da prepare_graphify_source.py. La lezione e' che il filtro sui
# nomi non e' un filtro sui contenuti, e che l'unico strato che poteva vedere
# queste tre stringhe era quello che ancora non esisteva.
#
# Il pattern e' volutamente largo sul lato del valore e stretto sul lato della
# chiave: preferisce scartare un'evidenza in piu' che lasciare passare un
# segreto, perche' il costo dei due errori non e' confrontabile.
# Forma di un valore che somiglia a una credenziale: almeno sei caratteri non
# spaziati con dentro una cifra o un simbolo in qualunque posizione, oppure una
# parola di almeno otto lettere, che copre le passphrase alfabetiche. Il vincolo
# sulla lunghezza si esprime con un lookahead invece che contando i caratteri
# prima e dopo il simbolo, perche' quella forma dipendeva da dove cadeva la cifra
# e mancava valori come "pippo123", dove le cifre stanno in fondo.
_SECRET_VALUE = (
    r"(?:(?=[^\s]{6,})[^\s]*[\d!@#$%^&*_+=][^\s]*|[A-Za-z]{8,})"
)

SECRET_PATTERNS = {
    # Fra la parola chiave e il separatore si ammettono pochi caratteri, perche'
    # nei documenti reali il valore e' spesso qualificato prima dei due punti,
    # come in "Credenziali RWS ID:" oppure "password del NAS:". Il limite tiene
    # la finestra corta per non agganciare due frasi diverse separate da un
    # capoverso, e la classe esclude i due punti proprio per fermarsi al primo.
    # Il valore deve avere la forma di una credenziale, non di una parola: almeno
    # sei caratteri con una cifra o un simbolo, oppure almeno dieci caratteri.
    # Senza questo vincolo la regola segnalava `token: write` nel workflow di
    # GitHub Actions, che e' un permesso, `Token cost: 4` in un report, e la voce
    # di menu "Password Management" di una pagina, cioe' tre falsi positivi che
    # rendono il verificatore rumoroso e quindi inutile: uno strumento che
    # segnala sempre qualcosa insegna a ignorarlo.
    "secret-assegnazione": re.compile(
        r"\b(?:password|passwd|pwd|pw|credenzial\w*|"
        r"chiave|api[\s_\-]?key|psk|passphrase|token|secret)\b"
        r"[^\n:=]{0,24}[:=]\s*" + _SECRET_VALUE,
        re.IGNORECASE,
    ),
    # Forme senza separatore, tipiche del parlato nei documenti operativi:
    # "la password e' pippo123", "con password pippo123".
    # La congiunzione `e` non e' ammessa fra le forme del verbo essere, benche' in
    # questo corpus l'accento sia spesso reso come apostrofo: in italiano "e" e'
    # la congiunzione, compare in ogni frase, e includerla faceva scartare la
    # descrizione di una policy di complessita' della password come se fosse una
    # password. Il valore deve inoltre somigliare a una credenziale, non essere
    # una parola qualsiasi.
    "secret-frase": re.compile(
        r"\b(?:password|passwd|pwd|credenzial\w*|passphrase|psk)\b"
        r"(?:\s+\w+){0,2}\s+(?:e'|era|sono|is|was)\s+" + _SECRET_VALUE,
        re.IGNORECASE,
    ),
    # Scheda di credenziali: la parola credenziali accostata a un identificativo
    # di utenza. Serve come regola distinta perche' non c'e' un valore da
    # riconoscere: il caso reale e' un'evidenza intitolata "Credenziali RWS ID:
    # email: ..." in cui la password sta oltre i trecento caratteri del preview,
    # quindi la regola sul valore non scatta ma il blocco e' comunque un
    # registro di accessi, e allentare la regola sul valore per prenderlo
    # riporterebbe i falsi positivi appena tolti.
    "secret-scheda-credenziali": re.compile(
        r"\b(?:credenzial\w*|credentials)\b[^\n]{0,30}"
        r"\b(?:id|login|utenza|account|user(?:name)?|e-?mail)\b",
        re.IGNORECASE,
    ),
    # File di deposito credenziali citati per nome: la loro sola menzione
    # accompagna quasi sempre il valore, e comunque indica dove cercarlo.
    "secret-file": re.compile(
        r"\b\w*(?:credenzial\w*|password|secret)\w*\.(?:crd|txt|docx?|xlsx?|kdbx|csv)\b",
        re.IGNORECASE,
    ),
}


# Residue patterns: se dopo anon il label li contiene ancora, la mappa ha
# mancato il caso specifico -> non lasciamolo passare comunque. Dict con
# etichetta esplicita cosi' il log dice esattamente perche' un item e' droppato.
#
# Le prime tre (IP/EMAIL/HOSTNAME) sono generiche. Le successive sono
# specifiche del contesto Intrawelt: nomi/domini/sede che la anonymization_map
# di enrich_graph non cattura perche' compaiono come varianti nude (senza
# suffisso ragione sociale) o come domini estratti da URL non tokenizzati.
# Se il progetto vuole coprire altre aziende, aggiungere qui i pattern
# corrispondenti.
LEAK_PATTERNS = {
    "residue-ip":       re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?\b"),
    "residue-email":    re.compile(r"\b[\w\.\-]+@[\w\.\-]+\.\w{2,}\b"),
    "residue-hostname": re.compile(
        r"\b("
        # WINDOWS scritto tutto maiuscolo non e' un hostname ma il nome del
        # sistema operativo, e in un corpus di helpdesk compare in ogni titolo:
        # senza questa esclusione il gate scartava evidenze buone e il
        # verificatore segnalava quattro pagine a ogni esecuzione.
        r"(?!WINDOWS\b)"
        r"WIN(?:SRV|GROUP|SERVER|DC|SQL|EX|HOST)?[A-Z0-9][A-Z0-9\-]{2,}"
        r"|SRV[-_]?[A-Z0-9][A-Z0-9\-]{1,}"
        r"|PC[-_][A-Z0-9][A-Z0-9\-]{1,}"
        r"|NAS[-_]?[A-Z0-9][A-Z0-9\-]{0,}"
        r"|USG[-_]?[A-Z0-9][A-Z0-9\-]{0,}"
        r"|VM\d{1,4}(?:[-_][A-Z0-9\-]+)?"
        r"|DC\d{1,2}(?:[-_][A-Z0-9\-]+)?"
        r")\b"
    ),
    "residue-domain-intrawelt":  re.compile(r"\bintrawelt\.(?:com|it|de)\b", re.IGNORECASE),
    # Dominio di un'azienda terza, cliente o fornitore, che nessuno strato a
    # monte cattura. Sta dopo la regola del dominio aziendale perche' l'ordine
    # del dizionario decide quale nome finisce nel report: intrawelt.com
    # matcherebbe anche qui, ma va imputato alla sua regola specifica.
    "residue-domain-third-party": THIRD_PARTY_DOMAIN_RE,
    # La ragione sociale nuda NON e' un residuo. Il datore di lavoro e'
    # dichiarato apertamente nella tassonomia pubblica ("IT team at Intrawelt
    # as IT Manager" in soft/index.md): trattarlo come segreto nelle evidenze
    # mentre la pagina di presentazione lo nomina non proteggeva nulla, e
    # costava evidenze buone scartate o scrubate. Resta invece residuo tutto
    # cio' che descrive l'infrastruttura o identifica persone: il dominio, le
    # email, gli IP, gli hostname, i fornitori e le sedi fisiche.
    # Il nome nudo di un fornitore NON e' piu' un residuo, dal 2026-08-03. Le
    # pagine pubbliche dichiarano volutamente a mano, nella sezione delle
    # tecnologie, quali sono i provider di hosting e di connettivita': lo stesso
    # nome era quindi curriculum in una sezione e segreto in quella accanto,
    # esattamente l'incoerenza risolta a luglio per la ragione sociale. La
    # distinzione adottata e' fra il nome, che dice con chi si lavora, e
    # l'identificativo di una macchina presso quel fornitore, che dice come si e'
    # fatti dentro: il primo passa, il secondo no, e lo ferma la regola
    # residue-provider-subdomain qui sotto. Per tornare indietro basta
    # reintrodurre qui i tre pattern per nome, che erano
    # `\bFastnet\b`, `\bpunto[\s\-_]*info` e `\bVianova\b`.
    "residue-provider-subdomain": PROVIDER_SUBDOMAIN_RE,
    # Clienti finali citati per nome nei documenti di lavoro. La ragione sociale
    # del datore di lavoro e' dichiarata apertamente nella tassonomia, quella di
    # un cliente no: e' un dato di terzi, e il nome di un cliente accostato a una
    # procedura interna dice anche quali sistemi quel cliente usa. Il pattern
    # COMPANY a monte non li cattura, perche' pretende un suffisso di forma
    # societaria e nei documenti il cliente compare come marchio nudo. La lista
    # si allunga quando un ciclo ne fa emergere altri, come e' successo con i
    # fornitori qui sopra.
    "residue-client-name":       re.compile(
        r"\b(?:Bayer|SAB\s+Aerospace|sabaerospace)\b", re.IGNORECASE),
    "residue-site-via-pescolla": re.compile(r"\bVia\s+Pescolla\b", re.IGNORECASE),
    "residue-site-elpidio":      re.compile(r"\bPorto\s+Sant['\s]?Elpidio\b", re.IGNORECASE),
    # Ottetto finale IP tra parentesi tipo '(.168)' o '(.177,' — forma sintetica
    # di graphify per abbreviare "192.168.20.168": non e' un IP full quindi il
    # regex dotted-quad non lo cattura, ma resta un leak parziale.
    "residue-ip-abbreviated":    re.compile(r"\(\.\d{1,3}\b"),
    # NAS INTRA / NAS INTRA2 / NAS INTRA3 / NAS FTP (con spazio o dash),
    # sfuggono al pattern HOSTNAME che vuole tutto uppercase attaccato.
    "residue-host-nas-named":    re.compile(r"\bNAS[\s\-]+(?:INTRA\d?|FTP|HERO)\b", re.IGNORECASE),
    # VM Ubuntu-YYYY-NAME (es. Ubuntu-1404-DOMV, Ubuntu-1204-eGetrad) — nome
    # macchina non-uppercase quindi HOSTNAME_RE non lo cattura.
    "residue-vm-ubuntu-named":   re.compile(r"\bUbuntu-\d{3,4}-[A-Za-z]{3,}\b"),
    # Applicativi/servizi interni citati per nome (eGetrad = gestionale storico).
    "residue-app-egetrad":       re.compile(r"\begetrad\b", re.IGNORECASE),
}


def apply_anon(text: str, anon_map: dict) -> str:
    if not text or not anon_map:
        return text
    for original in sorted(anon_map, key=len, reverse=True):
        text = re.sub(re.escape(original), anon_map[original], text)
    return text


def significant_chars(text: str) -> int:
    """Numero di caratteri alfanumerici esclusi i placeholder."""
    stripped = PLACEHOLDER_RE.sub("", text)
    return sum(1 for c in stripped if c.isalnum())


def build_person_token_rule(anon_map: dict) -> re.Pattern | None:
    """
    Costruisce dai nomi propri gia' presenti nella mappa una regola sui loro
    singoli token, e restituisce None se non ce n'e' abbastanza per farlo.

    Serve a chiudere una fuga scoperta nel ciclo Helpdesk RWS GroupShare Studio.
    La mappa sostituisce per stringa esatta, quindi copre "Daniela Landucci" ma
    non "Landucci" scritto da solo, e non copre affatto i nomi propri singoli,
    che l'estrazione scarta deliberatamente perche' un token isolato e' troppo
    ambiguo per essere mascherato a monte. Nei documenti reali le persone si
    citano pero' quasi sempre in forma parziale, per cognome nudo o per nome di
    battesimo, e il preview ancorato pesca esattamente quel tipo di frase: su
    questo corpus arrivavano nel testo pubblicabile un cognome e tre nomi di
    colleghe, piu' un elenco di reparto.

    La regola e' derivata dai dati e non da una lista scritta a mano, cosi' non
    serve versionare nomi di persona nel repository. Si contribuiscono solo i
    token delle voci che sono nomi di persona puliti, cioe' esattamente due
    parole alfabetiche con l'iniziale maiuscola: questo esclude le voci sporche
    prodotte da uno span troppo largo del riconoscitore, come "PC-SARA -
    Periodo", i cui token comuni danneggerebbero il testo. Il confronto e'
    sensibile al caso e ancorato ai confini di parola, perche' un token corto e
    minuscolo collide con parole italiane comuni.
    """
    tokens: set[str] = set()
    for original, placeholder in anon_map.items():
        if not placeholder.startswith("[PERSONA_"):
            continue
        parts = original.split()
        if len(parts) != 2:
            continue
        if not all(p.isalpha() and p[:1].isupper() for p in parts):
            continue
        for p in parts:
            if len(p) >= 4:
                tokens.add(p)
    if not tokens:
        return None
    alt = "|".join(re.escape(t) for t in sorted(tokens, key=len, reverse=True))
    return re.compile(rf"\b(?:{alt})\b")


def build_operator_rule(terms: list[str]) -> re.Pattern | None:
    """
    Costruisce la regola sui termini passati a mano dall'operatore, e
    restituisce None se non ne sono stati passati.

    Esiste perche' la regola derivata dalla mappa ha un limite di principio: un
    nome di persona che nel corpus compare soltanto in forma singola, mai come
    nome piu' cognome, non entra nella mappa e non ha quindi token da cui
    derivare. Su questo corpus erano tre, due nomi di battesimo e un cognome
    citati in frasi di lavoro. Il rimedio non puo' essere una lista scritta nel
    codice: versionare nomi di colleghi in un repository per proteggerli e' una
    contraddizione. Si passano invece sulla riga di comando, dove li mette la
    revisione manuale del diff che e' comunque obbligatoria, e restano fuori da
    git. Il confronto e' insensibile al caso, perche' qui il termine e' scelto da
    una persona e non dedotto, quindi il rischio di collisione e' valutato da
    chi lo passa.
    """
    clean = [t.strip() for t in terms if t.strip()]
    if not clean:
        return None
    alt = "|".join(re.escape(t) for t in sorted(clean, key=len, reverse=True))
    return re.compile(rf"\b(?:{alt})\b", re.IGNORECASE)


def runtime_patterns(anon_map: dict, extra_terms: list[str] | None = None) -> dict[str, re.Pattern]:
    """
    Restituisce i pattern statici piu' quello derivato dalla mappa.

    I pattern statici restano un dizionario di modulo perche' non dipendono dal
    corpus; quello sui token dei nomi propri si puo' costruire solo a runtime,
    quando la mappa esiste. Sta in coda cosi' che un residuo coperto anche da una
    regola specifica resti imputato a quella nel report.
    """
    patterns = dict(LEAK_PATTERNS)
    person_rule = build_person_token_rule(anon_map)
    if person_rule is not None:
        patterns["residue-person-token"] = person_rule
    operator_rule = build_operator_rule(extra_terms or [])
    if operator_rule is not None:
        patterns["residue-operator-term"] = operator_rule
    return patterns


def has_secret(*texts: str) -> str | None:
    """
    Ritorna il nome del primo pattern di segreto trovato in uno qualsiasi dei
    testi passati, oppure None.

    Si valuta sul testo grezzo e non su quello anonimizzato, perche' nessuna voce
    della mappa riguarda le credenziali e passare per l'anonimizzazione non
    cambierebbe l'esito ma aggiungerebbe solo un modo di sbagliare. Si valuta su
    tutti i campi insieme, label, nome del file e preview, perche' un segreto in
    uno qualunque di essi condanna l'intera evidenza.
    """
    for text in texts:
        if not text:
            continue
        for name, rx in SECRET_PATTERNS.items():
            if rx.search(text):
                return name
    return None


def has_residue(text: str, patterns: dict[str, re.Pattern] | None = None) -> str | None:
    """Ritorna il nome del primo pattern residuo trovato (o None)."""
    for name, rx in (patterns or LEAK_PATTERNS).items():
        if rx.search(text):
            return name
    return None


def scrub_residues(text: str, patterns: dict[str, re.Pattern] | None = None) -> tuple[str, list[str]]:
    """
    Sostituisce i residui trovati con un marcatore neutro, invece di scartare.

    Serve per i campi che accompagnano l'evidenza senza esserne il contenuto
    semantico: il nome del file sorgente e il preview del corpo. Su quelli lo
    scarto sarebbe sproporzionato, perche' una ragione sociale nel nome di un
    documento non rende l'evidenza inutilizzabile, la rende solo non
    pubblicabile cosi' com'e'. Sul label invece resta lo scarto, perche' un
    label scrubato rischia di non voler dire piu' niente.
    """
    found: list[str] = []
    out = text
    for name, rx in (patterns or LEAK_PATTERNS).items():
        if rx.search(out):
            found.append(name)
            out = rx.sub("[RIMOSSO]", out)
    return out, found


def evaluate_label(label: str, anon_map: dict, min_chars: int,
                   patterns: dict[str, re.Pattern] | None = None):
    """Ritorna (keep: bool, anon_label: str, reason: str)."""
    anon_label = apply_anon(label, anon_map)
    residue = has_residue(anon_label, patterns)
    if residue:
        return False, anon_label, residue
    if significant_chars(anon_label) < min_chars:
        return False, anon_label, "too-short-after-anon"
    return True, anon_label, "ok"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Filtra taxonomy_diff.json scartando entries con contenuto "
            "insufficiente o residui sensibili dopo anonimizzazione."
        )
    )
    parser.add_argument("--input",  required=True, help="Path a taxonomy_diff.json")
    parser.add_argument("--output", required=True, help="Path per taxonomy_diff sanitized")
    parser.add_argument("--extra-residue-terms", default="",
                        help="Termini aggiuntivi da trattare come residui, "
                             "separati da virgola. Serve ai nomi di persona che "
                             "nel corpus compaiono solo in forma singola e che "
                             "quindi non entrano nella mappa: li individua la "
                             "revisione manuale del diff e li passa qui, cosi' "
                             "non finiscono versionati nel repository.")
    parser.add_argument("--min-chars", type=int, default=10,
                        help="Minimo caratteri alfanumerici significativi nel label "
                             "dopo anonimizzazione (default 10)")
    args = parser.parse_args()

    in_path  = Path(args.input).resolve()
    out_path = Path(args.output).resolve()

    if not in_path.exists():
        print(f"ERRORE: input non trovato: {in_path}", file=sys.stderr)
        sys.exit(1)

    diff = json.loads(in_path.read_text(encoding="utf-8"))
    anon_map = diff.get("anonymization_map", {})

    if not anon_map:
        print(
            "AVVISO: taxonomy_diff.json senza anonymization_map. "
            "Il filtro applichera' comunque i pattern residui ma non le "
            "sostituzioni. Rigenera il diff con map_to_taxonomy aggiornato "
            "per anonimizzazione piena.",
            file=sys.stderr,
        )

    print(f"Input:       {in_path}", file=sys.stderr)
    print(f"anon-map:    {len(anon_map)} voci", file=sys.stderr)
    print(f"min-chars:   {args.min_chars}", file=sys.stderr)
    print("", file=sys.stderr)

    # -----------------------------------------------------------------------
    # Filtro
    # -----------------------------------------------------------------------
    stats = {
        "fit":            {"kept": 0, "dropped": {}, "examples_dropped": []},
        "new_capability": {"kept": 0, "dropped": {}, "examples_dropped": []},
        "new_domain":     {"kept": 0, "dropped": {}, "examples_dropped": []},
    }

    scrub_counts: dict[str, int] = {}
    dropped_node_keys: set[str] = set()

    extra_terms = args.extra_residue_terms.split(",") if args.extra_residue_terms else []
    patterns = runtime_patterns(anon_map, extra_terms)
    if "residue-person-token" in patterns:
        n_tok = patterns["residue-person-token"].pattern.count("|") + 1
        print(f"regola sui token dei nomi propri: {n_tok} token derivati "
              f"dalla mappa", file=sys.stderr)
    if "residue-operator-term" in patterns:
        print(f"termini passati dall'operatore: "
              f"{len([t for t in extra_terms if t.strip()])}", file=sys.stderr)
    print("", file=sys.stderr)

    def filter_bucket(items, kind):
        kept = []
        for item in items:
            if kind == "fit":
                node  = item.get("node", {})
                label = node.get("label", "")
            elif kind == "new_capability":
                label = item.get("suggested_name", "")
            elif kind == "new_domain":
                label = item.get("suggested_domain", "")
            else:
                label = ""

            keep, anon_label, reason = evaluate_label(label, anon_map, args.min_chars, patterns)

            # Il segreto si valuta per primo e su tutti i campi: se c'e', non
            # esiste nessuna forma in cui questa evidenza sia pubblicabile.
            node_for_secret = item.get("node", {}) if kind == "fit" else {}
            secret = has_secret(
                label,
                node_for_secret.get("source_file", ""),
                node_for_secret.get("text_preview", ""),
                *[n.get("label", "") for n in item.get("nodes", [])],
                *[n.get("text_preview", "") for n in item.get("nodes", [])],
            )
            if secret:
                keep, reason = False, secret

            # Il label non e' l'unico testo che finisce nella pagina pubblica:
            # ci finiscono anche il nome del file sorgente e il preview del
            # corpo. Entrambi passavano il gate senza controllo, ed e' da li'
            # che nel ciclo Cybersec endpoint sono uscite ragione sociale e
            # hostname nonostante la mappa di anonimizzazione. Qui si scrubano
            # invece di scartare, e si tiene il conto per il report.
            if keep and kind == "fit":
                node = item.get("node", {})
                for field in ("source_file", "text_preview"):
                    raw = node.get(field) or ""
                    if not raw:
                        continue
                    cleaned, found = scrub_residues(apply_anon(raw, anon_map), patterns)
                    if found:
                        node[field] = cleaned
                        for f in found:
                            scrub_counts[f] = scrub_counts.get(f, 0) + 1

            # Per new_capability: anche se il suggested_name e' pulito, i node
            # labels interni finiscono nel file (Responsibilities). Filtra i
            # nodes con residue e, se non ne rimane nessuno, droppa l'intera.
            if keep and kind == "new_capability":
                filtered_nodes = []
                for n in item.get("nodes", []):
                    n_label = n.get("label", "")
                    _, _, n_reason = evaluate_label(n_label, anon_map, min_chars=1, patterns=patterns)
                    if n_reason == "ok":
                        filtered_nodes.append(n)
                    # nodi troppo corti dopo anon: li teniamo (non sono un leak)
                    elif n_reason == "too-short-after-anon":
                        filtered_nodes.append(n)
                    # nodi con residue: droppati silenziosamente
                if not filtered_nodes:
                    keep, reason = False, "all-nodes-have-residue"
                else:
                    item["nodes"] = filtered_nodes

            if keep:
                kept.append(item)
                stats[kind]["kept"] += 1
            else:
                # Si registra la chiave del nodo scartato, non solo il conteggio.
                # Senza questo elenco il gate poteva impedire una pubblicazione
                # nuova ma non annullarne una vecchia: l'evidenza scartata
                # sparisce dal diff, quindi la passata di rimozione dell'export
                # non la vede nemmeno come nodo conosciuto e il blocco gia'
                # pubblicato resta orfano per sempre. E' cosi' che tre password
                # sarebbero rimaste sul sito anche dopo l'introduzione della
                # regola che le riconosce.
                node = item.get("node", {})
                key = node.get("id", node.get("label", "")) if node else ""
                if key:
                    dropped_node_keys.add(key)
                for n in item.get("nodes", []):
                    n_key = n.get("id", n.get("label", ""))
                    if n_key:
                        dropped_node_keys.add(n_key)
                stats[kind]["dropped"][reason] = stats[kind]["dropped"].get(reason, 0) + 1
                if len(stats[kind]["examples_dropped"]) < 5:
                    stats[kind]["examples_dropped"].append({
                        "original":   label[:120],
                        "anonymized": anon_label[:120],
                        "reason":     reason,
                    })
        return kept

    diff["fit"]            = filter_bucket(diff.get("fit",            []), "fit")
    diff["new_capability"] = filter_bucket(diff.get("new_capability", []), "new_capability")
    diff["new_domain"]     = filter_bucket(diff.get("new_domain",     []), "new_domain")

    # -----------------------------------------------------------------------
    # Riepilogo
    # -----------------------------------------------------------------------
    if scrub_counts:
        total = sum(scrub_counts.values())
        print(f"\nscrub su source_file/text_preview: {total} sostituzioni",
              file=sys.stderr)
        for name, count in sorted(scrub_counts.items(), key=lambda kv: -kv[1]):
            print(f"   {count:4d}  {name}", file=sys.stderr)
        print("   (residui sostituiti con [RIMOSSO], entries conservate)\n",
              file=sys.stderr)

    for kind in ("fit", "new_capability", "new_domain"):
        s = stats[kind]
        dropped_total = sum(s["dropped"].values())
        print(f"{kind:15s}: {s['kept']} kept, {dropped_total} dropped {s['dropped']}",
              file=sys.stderr)
        for ex in s["examples_dropped"]:
            print(f"   drop [{ex['reason']}]: "
                  f"'{ex['original']}' -> '{ex['anonymized']}'",
                  file=sys.stderr)

    diff["sanitization_stats"] = {
        kind: {k: v for k, v in stats[kind].items() if k != "examples_dropped"}
        for kind in stats
    }

    # Elenco delle chiavi di nodo scartate dal gate. Lo consuma la passata di
    # rimozione di export_to_taxonomy, che le tratta come nodi conosciuti dal
    # corpus e non piu' attesi da nessuna parte: e' questo che consente di
    # annullare una pubblicazione quando una regola nuova riconosce come non
    # pubblicabile qualcosa che era gia' uscito.
    diff["gate_dropped_nodes"] = sorted(dropped_node_keys)
    if dropped_node_keys:
        print(f"nodi scartati dal gate, dichiarati per la rimozione: "
              f"{len(dropped_node_keys)}", file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(diff, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nScritto: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
