"""Çekim modu: seçilen arızayı ya da lastik sorununu istenen anda tetikler (YouTube çekimleri; yalnızca tek oyunculu).

Ayarlar → Çekim modu: listeden arıza seçilir; "Şimdi tetikle" düğmesi ya da atanan kısayol tuşu (oyun penceresi öndeyken,
sürüş modu tuşu gibi atanır) onu hemen tetikler. Tetiklenen arıza rastgele çıkmış gibi işler: aynı uyarı metni, ikaz
lambası ve ses; aynı sonuçlar (hararet, akü boşalması, motorun durdurulması…); uygulamadan ve oyun içi servis
menüsünden aynı ücretle onarılır. Olay kaydında "elle" diye işaretlenir. "Hepsini onar" tüm arızaları ve lastik
hasarını ücretsiz giderir (çekim tekrarı için); sıvı seviyeleri, akü şarjı ve sıcaklıklar olduğu gibi kalır.
"""
from .faults import FAULTS
from .i18n import M, T, render
from .telltales import LABELS as LAMP_LABELS
from .tires import GROUP_NAMES

GROUPS = (("engine", "Motor ve yağlama"), ("cooling", "Soğutma"), ("electric", "Elektrik, marş ve ön ısıtma"),
          ("chassis", "Şanzıman, ABS ve direksiyon"), ("tires", "Lastikler"))
# (kimlik, grup, hemen yanan ikaz lambaları, belirtisi çıkınca yanan lambalar); lambalar kontak açıkken yanar
ITEMS = (
    ("oil_pump", "engine", ("oil", "stop"), ()),                 # yağ ve DURUN lambası motor çalışırken
    ("oil_leak", "engine", (), ("oil",)),
    ("head_gasket", "engine", ("eng",), ("cool",)),
    ("engine_seized", "engine", ("stop", "eng"), ()),
    ("thermostat_closed", "cooling", (), ("cool", "stop")),
    ("fan_clutch", "cooling", ("eng",), ("cool", "stop")),
    ("water_pump", "cooling", (), ("cool",)),
    ("thermostat_open", "cooling", ("eng",), ()),
    ("alternator", "electric", ("batt",), ()),
    ("starter", "electric", ("start",), ()),
    ("preheater", "electric", ("glow",), ()),
    ("abs_sensor", "chassis", ("abs",), ()),
    ("gearbox_cooler", "chassis", ("gear",), ()),
    ("clutch_actuator", "chassis", ("gear",), ()),
    ("steering_leak", "chassis", ("steer",), ()),
    ("blowout_front", "tires", ("tire", "stop"), ()),
    ("blowout_rear", "tires", ("tire", "stop"), ()),
    ("puncture_front", "tires", ("tire",), ()),
    ("puncture_rear", "tires", ("tire",), ()),
)
IDS = tuple(i[0] for i in ITEMS)
DEFAULT_ITEM = "oil_pump"
TIRE_ITEMS = {"blowout_front": ("blowout", "front"), "blowout_rear": ("blowout", "rear"),
              "puncture_front": ("puncture", "front"), "puncture_rear": ("puncture", "rear")}
TIRE_NAMES = {"blowout_front": "Lastik patlaması — ön dingil", "blowout_rear": "Lastik patlaması — arka dingil",
              "puncture_front": "Yavaş patlak — ön dingil", "puncture_rear": "Yavaş patlak — arka dingil"}
TIRE_DESCS = {
    "blowout": "Lastik aniden patlar: araç patlayan tarafa çeker, jant sürterek yavaşlar (oyun içi katman kurulu ve "
               "Ayarlar'da “Lastik patlaması” açıksa). Lastik değişimiyle giderilir.",
    "puncture": "Lastik yavaş yavaş hava kaçırır: basınç düştükçe lastik ısınır, sonunda patlayabilir. Yavaş patlak "
                "tamiriyle giderilir.",
}
PUNCTURE_BPH = 1.2   # elle yavaş patlağın hava kaçağı (bar/sa, 9 bar'lık lastiğe göre; rastgele patlakta 0,3–1,2)


def _axle(t, side):
    """Ön: yönlendirilen dingil (otomobilde ön lastikler) · arka: çekiş dingili (otomobilde arka), yoksa taşıyıcı."""
    for g in (("steer", "front") if side == "front" else ("drive", "rear", "tag")):
        s = t.tires.groups.get(g)
        if s and not s.get("lifted"):
            return g
    return None


def unavailable(t, item):
    """Bu araçta tetiklenemiyorsa nedeni (M), tetiklenebiliyorsa None. t None ise (oyun kapalı) yalnızca kimlik denetlenir."""
    if item not in IDS:
        return M("Bilinmeyen arıza.")
    if t is None:
        return None
    if item == "steering_leak" and t.veh == "car":
        return M("Otomobilde hidrolik direksiyon yok (elektrikli direksiyon).")
    if item == "preheater" and t.spec.fuel == "petrol":
        return M("Benzinli motorda ön ısıtma yok.")
    if item in TIRE_ITEMS and _axle(t, TIRE_ITEMS[item][1]) is None:
        return M("Bu dingil yok.")
    return None


def label(item):
    """Maddenin adı (Türkçe şablon; T ile çevrilir)."""
    return TIRE_NAMES[item] if item in TIRE_ITEMS else FAULTS[item]["name"]


def catalog(t=None):
    """Ayarlar'daki liste, seçili dilde. t: şu anki araç (bu araçta olmayanlar "available": False ve nedeni)."""
    items = []
    for k, g, now, later in ITEMS:
        if k in TIRE_ITEMS:
            desc, level = TIRE_DESCS[TIRE_ITEMS[k][0]], "crit" if TIRE_ITEMS[k][0] == "blowout" else "warn"
        else:
            desc, level = FAULTS[k]["desc"], FAULTS[k].get("level", "crit")
        why = unavailable(t, k)
        items.append({"id": k, "group": g, "label": T(label(k)), "desc": T(desc), "level": level,
                      "now": [T(LAMP_LABELS[x]) for x in now], "later": [T(LAMP_LABELS[x]) for x in later],
                      "available": why is None, "why": render(why) if why else ""})
    return {"groups": [{"key": g, "name": T(n)} for g, n in GROUPS], "items": items}


def trigger(t, f, item):
    """Seçilen arızayı hemen tetikler (rastgele çıkmış gibi; kayıtta elle diye işaretli). Dönüş: (başarılı, M ileti)."""
    why = unavailable(t, item)
    if why:
        return False, why
    if item in TIRE_ITEMS:
        return _tire(t, f, item)
    if not t.faults.add(item):
        return False, M("Bu arıza zaten var: {name_t}.", name_t=FAULTS[item]["name"])
    d = FAULTS[item]
    t.event(f, d.get("level", "crit"), M("ARIZA (elle tetiklendi): {name_t} — {desc_t}", name_t=d["name"],
                                         desc_t=d["desc"]), manual=True)
    if item == "engine_seized" and f.engine_on:
        # kendiliğinden kilitlenmedeki gibi: motor durdurulur (zorla durdurma ayarına uyulur: App.enforce_allowed)
        t.request_stop(f, M("Krank yatakları sardı, MOTOR KİLİTLENDİ."), manual=True)
    return True, M("Tetiklendi: {name_t}.", name_t=d["name"])


def _tire(t, f, item):
    kind, side = TIRE_ITEMS[item]
    g = _axle(t, side)
    s, grp = t.tires.groups[g], GROUP_NAMES[g]
    if s["blown"]:
        return False, M("Bu lastik zaten patlak: {grp_t}.", grp_t=grp)
    if kind == "blowout":
        s["blown"], s["cold_bar"], s["leak_bph"] = True, 0.0, 0.0
        t.event(f, "crit", M("LASTİK PATLADI ({grp_t}) — elle tetiklendi.", grp_t=grp), manual=True)
    else:
        if s["leak_bph"] > 0:
            return False, M("Bu lastikte zaten yavaş patlak var: {grp_t}.", grp_t=grp)
        s["leak_bph"] = PUNCTURE_BPH
        t.event(f, "warn", M("Yavaş patlak: {grp_t} lastiği hava kaçırıyor (elle tetiklendi).", grp_t=grp), manual=True)
    return True, M("Tetiklendi: {name_t}.", name_t=TIRE_NAMES[item])


def repair_all(t, f):
    """Tüm arızaları (elle ya da kendiliğinden çıkmış) ve lastik hasarını ücretsiz giderir; motor durdurma isteği
    kalkar. Sıvı seviyeleri, akü şarjı ve sıcaklıklar değişmez. Dönüş: (başarılı, M ileti)."""
    n = 0
    for k in list(t.faults.active):
        t.fix_part(k)
        n += 1
    for g, s in list(t.tires.groups.items()):
        if s["blown"]:
            t.tires.replace(g, s.get("tier", "premium"))     # patlayan lastik onarılmaz: aynı sınıftan yenisi
            n += 1
        elif s["leak_bph"] > 0:
            s["leak_bph"], s["cold_bar"] = 0.0, s["nominal"]
            n += 1
    stopped = t.killed
    t.killed, t.kill_reason, t.pending_stop = False, "", None
    t.health.starvation_s = t.health.seize_stress = t.health.head_gasket_stress = 0.0
    t.oil_low_s = 0.0
    if not n and not stopped:
        return False, M("Onarılacak arıza ya da lastik sorunu yok.")
    msg = M("Çekim modu: {n} arıza / lastik sorunu ücretsiz onarıldı.", n=n)
    t.event(f, "info", msg, kind="servis", manual=True)
    return True, msg
