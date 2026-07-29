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
    "residue-company-fastnet":   re.compile(r"\bFastnet\b", re.IGNORECASE),
    # Il separatore fra le due parole non e' sempre uno spazio: nei documenti
    # reali il fornitore compare anche come "Intrawelt-punto-info" e
    # "punto_informatica". Il pattern originale cercava `Punto\s+Informatica` e
    # mancava tutte le forme con trattino, underscore o troncate, che sono
    # emerse quando i preview hanno cominciato a pescare testo dal centro dei
    # documenti invece che dall'intestazione.
    "residue-vendor-punto-inf":  re.compile(r"\bpunto[\s\-_]*info", re.IGNORECASE),
    "residue-vendor-vianova":    re.compile(r"\bVianova\b", re.IGNORECASE),
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


def has_residue(text: str) -> str | None:
    """Ritorna il nome del primo pattern residuo trovato (o None)."""
    for name, rx in LEAK_PATTERNS.items():
        if rx.search(text):
            return name
    return None


def scrub_residues(text: str) -> tuple[str, list[str]]:
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
    for name, rx in LEAK_PATTERNS.items():
        if rx.search(out):
            found.append(name)
            out = rx.sub("[RIMOSSO]", out)
    return out, found


def evaluate_label(label: str, anon_map: dict, min_chars: int):
    """Ritorna (keep: bool, anon_label: str, reason: str)."""
    anon_label = apply_anon(label, anon_map)
    residue = has_residue(anon_label)
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

            keep, anon_label, reason = evaluate_label(label, anon_map, args.min_chars)

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
                    cleaned, found = scrub_residues(apply_anon(raw, anon_map))
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
                    _, _, n_reason = evaluate_label(n_label, anon_map, min_chars=1)
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

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(diff, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nScritto: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
