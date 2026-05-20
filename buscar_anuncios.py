#!/usr/bin/env python3
import requests, json, base64, os, time
from datetime import datetime
from duckduckgo_search import DDGS

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GH_PAT           = os.environ["GH_PAT"]
GITHUB_REPO      = "Guxtavo203/Agente-Anuncios"
META_TOKEN       = os.environ.get("META_ADS_TOKEN", "")
MEMORY_FILE      = "sent_ads.json"
TODAY            = datetime.now().strftime("%d/%m/%Y")

KEYWORDS = [
    "anuncio video produto digital renda online brasil instagram 2026",
    "IAS inteligencia artificial afiliado anuncio viral brasil",
    "facebook ads produto digital brasil renda extra 2026",
    "anuncio viral instagram infoproduto afiliado brasil maio 2026",
    "video ad digital product online income brazil viral 2026",
    "site:facebook.com/ads/library produto digital brasil",
    "site:facebook.com/ads/library renda online afiliado brasil",
]

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }, timeout=30)
    time.sleep(1)
    return r.ok

def get_memory():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{MEMORY_FILE}"
    r = requests.get(url, headers={"Authorization": f"token {GH_PAT}"}, timeout=30)
    if r.status_code == 404:
        return [], None
    data = r.json()
    content = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    return content, data["sha"]

def update_memory(ads_list, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{MEMORY_FILE}"
    content = base64.b64encode(json.dumps(ads_list, ensure_ascii=False, indent=2).encode()).decode()
    body = {"message": f"Update sent ads {datetime.now().strftime('%Y-%m-%d')}", "content": content}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers={
        "Authorization": f"token {GH_PAT}",
        "Content-Type": "application/json"
    }, json=body, timeout=30)
    return r.status_code in [200, 201]

def search_meta_api(keyword):
    if not META_TOKEN:
        return []
    url = "https://graph.facebook.com/v19.0/ads_archive"
    params = {
        "access_token": META_TOKEN,
        "search_terms": keyword,
        "ad_type": "ALL",
        "ad_reached_countries": "BR",
        "fields": "id,ad_creative_body,page_name,ad_delivery_start_time",
        "limit": 10,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        ads = []
        for ad in r.json().get("data", []):
            ads.append({
                "url": f"https://www.facebook.com/ads/library/?id={ad.get('id','')}",
                "title": ad.get("page_name", "Desconhecido"),
                "body": (ad.get("ad_creative_body") or "")[:300],
                "start": ad.get("ad_delivery_start_time", ""),
                "source": "Meta API oficial",
            })
        return ads
    except Exception as e:
        print(f"Meta API erro: {e}")
        return []

def search_ddg(keyword):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(keyword, region="br-pt", max_results=8))
        ads = []
        for r in results:
            ads.append({
                "url": r.get("href", ""),
                "title": r.get("title", ""),
                "body": r.get("body", "")[:300],
                "source": "Busca web",
            })
        return ads
    except Exception as e:
        print(f"DDG erro com '{keyword}': {e}")
        return []

def is_relevant(ad):
    text = (ad.get("title","") + " " + ad.get("body","")).lower()
    keywords = ["produto digital","renda","afiliado","ias","intelig","anuncio",
                "ad ","ads","vender","ganhar","online","infoproduto","marketing",
                "facebook","instagram","video","viral","method","sistema"]
    return any(k in text for k in keywords)

def analyze_ad(ad):
    body = ad.get("body","") or ad.get("title","")
    hook = body[:130].strip() if body else "Ver no link"
    bl = body.lower()
    parts = []
    if any(w in bl for w in ["problema","cansado","frustrado","dificil","nao consegue","sofrendo"]):
        parts.append("Problema")
    if any(w in bl for w in ["solucao","metodo","sistema","descubra","aprenda","segredo","formula"]):
        parts.append("Solucao")
    if any(w in bl for w in ["clique","acesse","saiba mais","compre","garanta","link","cadastre"]):
        parts.append("CTA")
    structure = " → ".join(parts) if parts else "Hook direto → Beneficio → CTA"
    return hook, structure

def main():
    print(f"=== Buscando anuncios virais - {TODAY} ===")
    sent_ads, sha = get_memory()
    sent_urls = {a["url"] for a in sent_ads if a.get("url")}
    print(f"Ja enviados anteriormente: {len(sent_urls)}")

    all_ads = []

    # Meta API (se token disponivel)
    if META_TOKEN:
        print("Buscando via Meta Ads API...")
        for kw in ["produto digital", "IAS inteligencia artificial", "renda online afiliado", "infoproduto"]:
            results = search_meta_api(kw)
            print(f"  Meta '{kw}': {len(results)} resultados")
            all_ads.extend(results)

    # DuckDuckGo
    print("Buscando via DuckDuckGo...")
    for kw in KEYWORDS:
        results = search_ddg(kw)
        print(f"  DDG '{kw[:40]}': {len(results)} resultados")
        all_ads.extend(results)
        time.sleep(2)

    # Filtrar relevantes e novos
    seen, new_ads = set(), []
    for ad in all_ads:
        url = ad.get("url","")
        if not url or url in sent_urls or url in seen:
            continue
        if is_relevant(ad):
            seen.add(url)
            new_ads.append(ad)

    print(f"Novos e relevantes: {len(new_ads)}")

    if not new_ads:
        send_telegram(
            f"📊 <b>Analise do dia — {TODAY}</b>\n\n"
            "Nenhum anuncio ou conteudo novo relevante encontrado hoje no nicho de produto digital/IAS/renda online.\n"
            "Os conteudos em circulacao sao os mesmos de dias anteriores.\n"
            "Voltamos amanha as 9h! ✅"
        )
        return

    # Cabecalho
    source_note = "Meta Ad Library oficial 🎯" if META_TOKEN else "Busca web (sem Meta API)"
    send_telegram(
        f"🔥 <b>ANUNCIOS VIRAIS DO DIA — {TODAY}</b>\n\n"
        f"🇧🇷 Nicho: Produto Digital / IAS / Renda Online\n"
        f"📡 Fonte: {source_note}\n"
        f"📌 {len(new_ads[:8])} novos encontrados hoje"
    )

    new_entries = []
    for i, ad in enumerate(new_ads[:8], 1):
        hook, structure = analyze_ad(ad)
        title = ad.get("title","Anunciante desconhecido")[:60]
        url = ad.get("url","")
        source = ad.get("source","Web")
        start = ad.get("start","")

        msg = f"📌 <b>ANUNCIO {i}</b>\n"
        msg += f"👤 <b>{title}</b>\n"
        msg += f"🎯 Hook: {hook}\n"
        msg += f"📋 Estrutura: {structure}\n"
        msg += f"📡 Fonte: {source}\n"
        if start:
            msg += f"📅 Ativo desde: {start[:10]}\n"
        if url:
            msg += f"🔗 {url}"

        send_telegram(msg)
        if url:
            new_entries.append({"url": url, "date_sent": datetime.now().strftime("%Y-%m-%d")})

    updated = (sent_ads + new_entries)[-500:]
    if update_memory(updated, sha):
        print(f"Memoria atualizada: +{len(new_entries)} registros")

if __name__ == "__main__":
    main()