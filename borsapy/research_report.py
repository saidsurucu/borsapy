"""Self-contained, escaped HTML output for the value research command."""

from html import escape


def render_report(payload: dict) -> str:
    records, meta = payload["companies"], payload["metadata"]

    def number(value, suffix=""):
        return (
            "—" if value is None else f"{value:,.2f}".translate(str.maketrans(",.", ".,")) + suffix
        )

    rows = []
    details = []
    for row in records:
        symbol = escape(row["symbol"])
        metric = "PD/DD" if row.get("primary_metric") == "reported_pb" else "F/K"
        value = row.get(row.get("primary_metric") or "common_basis_pe")
        rows.append(
            f'<tr data-status="{escape(row["status"], quote=True)}">'
            f'<td><a href="#{symbol}">{symbol}</a><small>{escape(row["name"])}</small></td>'
            f"<td>{escape(row['sector'])}</td><td>{metric} {number(value)}</td>"
            f"<td>{number(row.get('peer_median'))}<small>{row['peer_count']} akran</small></td>"
            f"<td>{number(row.get('peer_discount_pct'), '%')}</td>"
            f"<td>{number(row.get('real_revenue_growth_pct'), '%')}</td>"
            f"<td>{escape(row.get('report_period') or '—')}</td>"
            f"<td>{escape(row['status'])}</td></tr>"
        )
        latest = row.get("latest_report") or {}
        annual = row.get("annual_report") or {}
        links = [f'<a href="{escape(row["market_source"], quote=True)}">Piyasa verisi</a>']
        for label, report in (("Son KAP raporu", latest), ("Önceki yıllık rapor", annual)):
            if report.get("source_url"):
                links.append(f'<a href="{escape(report["source_url"], quote=True)}">{label}</a>')
            if report.get("pdf_url"):
                links.append(f'<a href="{escape(report["pdf_url"], quote=True)}">{label} PDF</a>')
        flags = "".join(f"<li>{escape(flag)}</li>" for flag in row["flags"])
        details.append(
            f'<details id="{symbol}"><summary>{symbol} · {escape(row["name"])}</summary>'
            f"<p>{' · '.join(links)}</p>"
            f"<p>Doğrulanan satın alma gücü ayı: <b>{escape(row.get('basis_month') or 'Doğrulanamadı')}</b>. "
            f"Kaynak F/K: {number(row.get('reported_pe'))}; kaynak PD/DD: {number(row.get('reported_pb'))}; "
            f"kaynak FD/FAVÖK: {number(row.get('reported_ev_ebitda'))}.</p>"
            f"<p>Ortak baz TTM ana ortaklık kârı: {number(row.get('ttm_parent_profit'))} TL; "
            f"faaliyet nakdi: {number(row.get('ttm_operating_cash'))} TL.</p>"
            f"<ul>{flags}</ul></details>"
        )
    candidates = sum(r["status"] == "İnceleme adayı" for r in records)
    verified = sum(r.get("basis_month") is not None for r in records)
    comparable = sum(r.get("common_basis_pe") is not None for r in records)
    unread = sum(not r.get("latest_report") for r in records)
    coverage = (
        f"{unread} şirketin KAP raporu alınamadı veya desteklenen biçimde okunamadı. "
        if unread
        else ""
    )
    if not candidates:
        coverage += "Aday çıkmaması, ucuz hisse olmadığı anlamına gelmez; eksik veri ve akran sayısı sonuçları sınırlar."
    methodology = "".join(f"<li>{escape(line)}</li>" for line in meta["methodology"])
    generated = escape(meta["generated_at"])
    partial = " · Kısmi evren" if meta["partial_universe"] else ""
    options = "".join(
        f"<option>{escape(status)}</option>" for status in sorted({r["status"] for r in records})
    )
    return f"""<!doctype html>
<html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BIST 100 · Şirket araştırması</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f3ee;color:#202b28;font:15px/1.55 system-ui,sans-serif}}
main{{max-width:1500px;margin:auto;padding:40px 28px}}h1{{font-size:36px;margin:8px 0}}p{{max-width:1000px}}
a{{color:#14674b}}.eyebrow{{letter-spacing:.12em;text-transform:uppercase;font-size:12px}}
.stats{{display:flex;flex-wrap:wrap;gap:40px;padding:24px 0;border-block:1px solid #d4dbd4;margin:24px 0}}.stats b{{display:block;font-size:30px}}
.stats span,small{{color:#64716a}}small{{display:block;font-size:11px;max-width:190px}}
.controls{{display:flex;gap:12px;margin:24px 0}}input,select{{background:white;border:1px solid #bbc8bf;padding:11px;font:inherit;border-radius:4px}}
input{{flex:1;max-width:440px}}.scroll{{overflow-x:auto;background:#fff;border:1px solid #d4dbd4}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{padding:14px 12px;text-align:left;border-bottom:1px solid #e4e9e5;vertical-align:top}}
th{{background:#e9eee8;white-space:nowrap}}td:first-child a{{font-weight:700}}tr:hover{{background:#f5f8f4}}
details{{padding:16px 0;border-bottom:1px solid #d4dbd4}}summary{{cursor:pointer;font-weight:600}}li{{margin:8px 0}}
.note{{border-left:3px solid #8e9864;padding-left:14px}}footer{{margin-top:30px;font-size:12px;color:#64716a}}
@media(max-width:650px){{main{{padding:22px 14px}}h1{{font-size:28px}}.stats{{gap:20px}}.controls{{flex-direction:column}}}}
</style><main><div class="eyebrow">BIST 100 / Araştırma defteri{partial}</div>
<h1>Fiyatın arkasındaki şirket.</h1>
<p>Sektör içindeki çarpanları, raporun satın alma gücü bazını ve kârın nakde dönüşmesini birlikte incele.
Eksik bilgi sıfır kabul edilmez; doğrulanamayan hesaplar boş bırakılır.</p>
<p style="font-size:12px;color:#64716a">Veri çekimi: {generated}. Fiyatların işlem zamanı kaynakta belirtilmiyor.</p>
<div class="stats"><div><b>{len(records)}</b><span>şirket</span></div>
<div><b>{verified}</b><span>rapor bazı doğrulandı</span></div>
<div><b>{comparable}</b><span>ortak baz F/K hesaplandı</span></div><div><b>{candidates}</b><span>inceleme adayı</span></div></div>
<p class="note">{coverage}</p>
<p class="note">İndirim, diğer şirketlerin çarpan medyanına göredir; hedef fiyat veya beklenen getiri değildir.
Ara dönem TTM değerleri, raporlar arası muhasebe değişikliklerini uzlaştırmayan TÜFE tahminleridir.</p>
<div class="controls"><input id="search" aria-label="Şirket veya sektör ara" placeholder="Şirket veya sektör ara…">
<select id="status" aria-label="Durum filtresi"><option value="">Tüm şirketler</option>
{options}</select>
<span id="count" aria-live="polite">{len(records)} şirket</span></div>
<div class="scroll"><table><thead><tr><th>Şirket</th><th>Sektör</th><th>Çarpan</th><th>Akran medyanı</th>
<th>Göreli indirim</th><th>Reel satış büyümesi</th><th>Rapor dönemi</th><th>Durum</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<h2>Hesaplama ve kapsam</h2><ul>{methodology}</ul>
<p><b>F/K</b>, şirketin piyasa değerinin yıllık kârına oranıdır. <b>PD/DD</b>, piyasa değerinin
özkaynağa oranıdır. Düşük bir oran büyüme veya risk farkından da kaynaklanabilir.
<b>Faaliyet nakdi</b>, şirketin işinden ürettiği nakittir; muhasebe kârının nakitle desteklenip
desteklenmediğini incelemeye yardımcı olur. <b>TTM</b>, son 12 ay demektir.</p>
<p>Sayısal hesapların bileşenleri ve kaynakları <a href="bist100-research.json">JSON dosyasında</a>;
tablo <a href="bist100-research.csv">CSV dosyasında</a> bulunur.</p>
<h2>Şirket kaynakları ve kontrol notları</h2>{"".join(details)}
<footer>Çekilme zamanı: {generated}. Kaynağın işlem zamanı doğrulanmamıştır.</footer></main>
<script>
const search=document.getElementById('search'),status=document.getElementById('status');
function searchText(value){{return value.toLocaleLowerCase('tr').replaceAll('ı','i').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'');}}
function filter(){{let count=0;const term=searchText(search.value);
document.querySelectorAll('tbody tr').forEach(row=>{{const show=searchText(row.textContent).includes(term)&&(!status.value||row.dataset.status===status.value);
row.hidden=!show;if(show)count++;}});document.getElementById('count').textContent=count+' şirket';}}
search.addEventListener('input',filter);status.addEventListener('change',filter);
document.querySelectorAll('tbody a').forEach(a=>a.addEventListener('click',()=>{{const detail=document.getElementById(a.hash.slice(1));if(detail)detail.open=true;}}));
</script></html>"""
