#!/usr/bin/env python3
"""Seed Mac DB with test passwords + full graph dummy data."""
import sqlite3, hashlib, os, json, random, sys
from datetime import datetime, timezone, timedelta

DB = sys.argv[1] if len(sys.argv) > 1 else "tfael_omni.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

# 1. Set test passwords — baca dari env OMNI_SEED_PASSWORD, default acak
_default_pwd = os.environ.get("OMNI_SEED_PASSWORD", "")
if not _default_pwd:
    import secrets as _sec
    _default_pwd = _sec.token_urlsafe(12)
    print(f"[SEED] Password acak untuk semua user: {_default_pwd}")

SEED_USERS = ["komandan", "analis.intel", "operator.c2", "admin.sistem", "auditor.itjen"]
for user in SEED_USERS:
    pwd = os.environ.get(f"OMNI_SEED_PWD_{user.upper().replace(chr(46),chr(95))}", _default_pwd)
    salt = os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt.encode("utf-8"), 120000).hex()
    cur.execute("UPDATE rbac_users SET salt=?, pwd_hash=? WHERE username=?", (salt, h, user))
print("Passwords set")

# 2. Seed graph
def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def rand_past(hours=720):
    return (datetime.now(timezone.utc) - timedelta(hours=random.randint(1, hours))).strftime("%Y-%m-%dT%H:%M:%SZ")

cur.execute("DELETE FROM graph_nodes")
cur.execute("DELETE FROM graph_edges")
now = now_iso()

nodes = [
    ("TGT-ALPHA","person","Ahmad Fauzan",{"risk_score":8.5,"risk_level":"critical","alias":"abu_shark","country":"ID"}),
    ("TGT-BRAVO","person","Budi Santoso",{"risk_score":6.2,"risk_level":"high","alias":"b_santo","country":"ID"}),
    ("TGT-CHARLIE","person","Chen Wei",{"risk_score":4.1,"risk_level":"medium","alias":"cw_ghost","country":"CN"}),
    ("TGT-DELTA","person","Dewi Lestari",{"risk_score":2.0,"risk_level":"low","country":"ID"}),
    ("TGT-ECHO","person","Evgeny Petrov",{"risk_score":7.8,"risk_level":"high","alias":"ev_shadow","country":"RU"}),
    ("user:abu_shark","username","abu_shark",{"platform":"Telegram","verified":True}),
    ("user:b_santo","username","b_santo",{"platform":"Telegram","verified":True}),
    ("user:cw_ghost","username","cw_ghost",{"platform":"Signal","verified":False}),
    ("user:ev_shadow","username","ev_shadow",{"platform":"WhatsApp","verified":True}),
    ("user:dark_admin","username","dark_admin",{"platform":"Forum XSS","verified":False}),
    ("email:fauzan.ahmad@proton.me","email","fauzan.ahmad@proton.me",{"provider":"ProtonMail"}),
    ("email:budi.s@gmail.com","email","budi.s@gmail.com",{"provider":"Gmail"}),
    ("email:cw_ops@tutanota.com","email","cw_ops@tutanota.com",{"provider":"Tutanota"}),
    ("email:ev.petrov@yandex.ru","email","ev.petrov@yandex.ru",{"provider":"Yandex"}),
    ("domain:darkops.net","domain","darkops.net",{"registrar":"Namecheap","status":"active"}),
    ("domain:securecomms.id","domain","securecomms.id",{"registrar":"Rumahweb","status":"active"}),
    ("domain:fastdrop.io","domain","fastdrop.io",{"registrar":"Cloudflare","status":"suspended"}),
    ("ip:185.220.101.42","ip","185.220.101.42",{"geo":"Netherlands","asn":"AS47147","isp":"TOR Exit Node","is_tor":True}),
    ("ip:103.28.148.9","ip","103.28.148.9",{"geo":"Indonesia","asn":"AS132802","isp":"CloudHost"}),
    ("ip:45.77.65.210","ip","45.77.65.210",{"geo":"Japan","asn":"AS20473","isp":"Vultr"}),
    ("ip:91.219.236.180","ip","91.219.236.180",{"geo":"Russia","asn":"AS48287","isp":"ShadowHost"}),
    ("ip:198.51.100.25","ip","198.51.100.25",{"geo":"USA","asn":"AS13335","isp":"Cloudflare CDN"}),
    ("phone:+6281234567890","phone","+6281234567890",{"carrier":"Telkomsel","country":"ID"}),
    ("phone:+6285678901234","phone","+6285678901234",{"carrier":"XL Axiata","country":"ID"}),
    ("phone:+79161234567","phone","+79161234567",{"carrier":"MTS Russia","country":"RU"}),
    ("org:shadow_network","organization","Shadow Network Cell",{"type":"criminal","threat_level":"critical"}),
    ("org:pt_maju_jaya","organization","PT Maju Jaya Sentosa",{"type":"front_company","threat_level":"high"}),
    ("loc:-6.2088,106.8456","location","Jakarta Pusat",{"lat":-6.2088,"lon":106.8456}),
    ("loc:-7.2575,112.7521","location","Surabaya",{"lat":-7.2575,"lon":112.7521}),
    ("loc:55.7558,37.6173","location","Moscow",{"lat":55.7558,"lon":37.6173}),
    ("svc:darkops.net:22","service","SSH:22 (darkops.net)",{"port":22,"proto":"tcp"}),
    ("svc:darkops.net:443","service","HTTPS:443 (darkops.net)",{"port":443,"proto":"tcp"}),
    ("svc:securecomms.id:8443","service","API:8443 (securecomms.id)",{"port":8443,"proto":"tcp"}),
    ("breach:linkedin_2021","breach","LinkedIn 2021 Leak",{"records":700000000,"date":"2021-04-06"}),
    ("breach:tokped_2020","breach","Tokopedia 2020",{"records":91000000,"date":"2020-05-02"}),
]

for nid, ntype, label, props in nodes:
    cur.execute("INSERT OR REPLACE INTO graph_nodes (node_id,node_type,label,properties,source_module,first_seen,last_seen) VALUES (?,?,?,?,?,?,?)",
        (nid, ntype, label, json.dumps(props), "osint", rand_past(), now))

edges = [
    ("TGT-ALPHA","user:abu_shark","uses_handle"),("TGT-BRAVO","user:b_santo","uses_handle"),
    ("TGT-CHARLIE","user:cw_ghost","uses_handle"),("TGT-ECHO","user:ev_shadow","uses_handle"),
    ("TGT-ALPHA","email:fauzan.ahmad@proton.me","uses_email"),("TGT-BRAVO","email:budi.s@gmail.com","uses_email"),
    ("TGT-CHARLIE","email:cw_ops@tutanota.com","uses_email"),("TGT-ECHO","email:ev.petrov@yandex.ru","uses_email"),
    ("TGT-ALPHA","phone:+6281234567890","uses_phone"),("TGT-BRAVO","phone:+6285678901234","uses_phone"),
    ("TGT-ECHO","phone:+79161234567","uses_phone"),
    ("TGT-ALPHA","org:shadow_network","member_of"),("TGT-BRAVO","org:pt_maju_jaya","director_of"),
    ("TGT-CHARLIE","org:shadow_network","member_of"),("TGT-ECHO","org:shadow_network","leader_of"),
    ("TGT-ALPHA","loc:-6.2088,106.8456","located_in"),("TGT-BRAVO","loc:-7.2575,112.7521","located_in"),
    ("TGT-ECHO","loc:55.7558,37.6173","located_in"),("TGT-DELTA","loc:-6.2088,106.8456","located_in"),
    ("TGT-ALPHA","TGT-BRAVO","communicates_with"),("TGT-ALPHA","TGT-ECHO","communicates_with"),
    ("TGT-BRAVO","TGT-CHARLIE","communicates_with"),("TGT-CHARLIE","TGT-ECHO","communicates_with"),
    ("TGT-DELTA","TGT-BRAVO","associated_with"),
    ("domain:darkops.net","ip:185.220.101.42","resolves_to"),("domain:securecomms.id","ip:103.28.148.9","resolves_to"),
    ("domain:fastdrop.io","ip:45.77.65.210","resolves_to"),
    ("user:dark_admin","domain:darkops.net","admin_of"),("user:abu_shark","domain:fastdrop.io","registered"),
    ("email:budi.s@gmail.com","breach:tokped_2020","exposed_in"),("email:fauzan.ahmad@proton.me","breach:linkedin_2021","exposed_in"),
    ("ip:185.220.101.42","svc:darkops.net:22","hosts"),("ip:185.220.101.42","svc:darkops.net:443","hosts"),
    ("ip:103.28.148.9","svc:securecomms.id:8443","hosts"),
    ("ip:185.220.101.42","ip:91.219.236.180","tunnels_to"),("ip:91.219.236.180","ip:45.77.65.210","proxied_via"),
    ("org:shadow_network","domain:darkops.net","operates"),("org:pt_maju_jaya","domain:securecomms.id","owns"),
    ("user:abu_shark","ip:185.220.101.42","logged_from"),("user:ev_shadow","ip:91.219.236.180","logged_from"),
    ("user:cw_ghost","ip:45.77.65.210","logged_from"),
]

for src, tgt, rel in edges:
    cur.execute("INSERT OR REPLACE INTO graph_edges (source_id,target_id,rel_type,properties,source_module,confidence,first_seen,last_seen) VALUES (?,?,?,?,?,?,?,?)",
        (src, tgt, rel, "{}", "osint", round(random.uniform(0.6,1.0),2), rand_past(), now))

# Seed target_profiles
for nid, ntype, label, props in [n for n in nodes if n[1]=="person"]:
    cur.execute("""INSERT OR REPLACE INTO target_profiles
        (target_id,code_name,real_name,category,primary_domain,primary_ip,
         cyber_score,spatial_score,visual_score,forensic_score,risk_score,risk_level,
         osint_json,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (nid, props.get("alias",""), label, "HOSTILE" if props.get("risk_score",0)>=5 else "POI",
         "","", random.randint(30,90),random.randint(20,80),random.randint(10,70),random.randint(15,60),
         int(props.get("risk_score",0)*10), props.get("risk_level","low"),
         json.dumps({"country":props.get("country",""),"alias":props.get("alias","")}), now))

conn.commit()
nc = cur.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
ec = cur.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
print(f"Seeded {nc} nodes, {ec} edges")
conn.close()
