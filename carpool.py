import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import os
import random
from branca.element import MacroElement
from jinja2 import Template

st.set_page_config(page_title="Mitfahrbörse", layout="wide")
st.title("🚗 Mitfahrbörse")

DATA_FILE = "personen.json"
GROUP_FILE = "gruppen.json"

# ---- Helpers ----
def load_json(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def clear_data():
    save_json(DATA_FILE, [])
    save_json(GROUP_FILE, [])

PALETTE = ["#FF0000","#0077FF","#00CC44","#FF9900","#9933FF",
           "#00CED1","#FF1493","#8B4513","#FFD700","#008B8B"]
def random_color():
    return random.choice(PALETTE)

personen = load_json(DATA_FILE)
gruppen = load_json(GROUP_FILE)

# ---- Passwortloser Login ----
st.sidebar.header("🔐 Anmeldung")
if "user" not in st.session_state:
    st.session_state["user"] = None

if st.session_state["user"] is None:
    temp_name = st.sidebar.text_input("Dein Name", placeholder="Vorname und Nachname")
    if st.sidebar.button("Anmelden"):
        if not temp_name or not temp_name.strip():
            st.sidebar.warning("Bitte einen Namen eingeben.")
        else:
            st.session_state["user"] = temp_name.strip()
            st.sidebar.success(f"Angemeldet als: {st.session_state['user']}")
else:
    st.sidebar.write(f"👋 Angemeldet als **{st.session_state['user']}**")
    if st.sidebar.button("Abmelden"):
        st.session_state["user"] = None

st.sidebar.markdown("---")
st.sidebar.markdown("Hinweis: Passwortloser Login. Namen sind eindeutig.")

# ---- 1) Deine Teilnahme ----
st.subheader("👤 Deine Teilnahme")
if st.session_state["user"] is None:
    st.info("Bitte melde dich links in der Seitenleiste an.")
    username = None
    role = None
    freie_plaetze = 0
else:
    username = st.session_state["user"]
    existing = next((p for p in personen if p["name"] == username), None)
    st.markdown(f"**Angemeldet als:** {username}")

    # Radio für Rolle
    role_default = existing["role"] if existing else "Mitfahrer (suche Platz)"
    role = st.radio(
        "Ich bin …",
        ["Fahrer (biete Plätze an)", "Mitfahrer (suche Platz)"],
        index=0 if "Fahrer" in role_default else 1
    )

    # Freie Plätze nur für Fahrer
    if "Fahrer" in role:
        default_plaetze = max(1, existing["freie_plaetze"]) if existing else 3
        freie_plaetze = st.number_input(
            "Wie viele Plätze hast du frei?",
            min_value=1,
            max_value=8,
            value=default_plaetze
        )
    else:
        freie_plaetze = 0

st.info("Klicke auf die Karte, um deinen Standort zu wählen. Dein Pin erscheint nach ein paar Sekunden. Dann '✅ Mich eintragen' klicken.")

# ---- 2) Karte ----
if "last_click" not in st.session_state:
    st.session_state["last_click"] = None

m = folium.Map(location=[53.6, 9.9], zoom_start=8)

for p in personen:
    color = "green" if "Fahrer" in p["role"] else "blue"
    folium.Marker(
        [p["lat"], p["lon"]],
        popup=f"{p['name']} ({p['role']})",
        icon=folium.Icon(color=color)
    ).add_to(m)

legende_html = "<b>🎨 Fahrgemeinschaften</b><br>"
for gruppe in gruppen:
    color = gruppe.get("color", random_color())
    members = [p for p in personen if p["name"] in gruppe.get("mitglieder", [])]
    coords = [(p["lat"], p["lon"]) for p in members]
    if len(coords) > 1:
        folium.PolyLine(coords, color=color, weight=5, opacity=0.8, tooltip=gruppe["name"]).add_to(m)
        legende_html += f'<i style="background:{color};width:18px;height:18px;border-radius:4px;display:inline-block;margin-right:5px;"></i>{gruppe["name"]}<br>'

if gruppen:
    legend = MacroElement()
    legend._template = Template(f"""
        <div style="
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index:9999;
            background-color: white;
            padding: 10px 15px;
            border: 2px solid #666;
            border-radius: 10px;
            font-size: 14px;
            box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
        ">
        {legende_html}
        </div>
    """)
    m.get_root().add_child(legend)

if st.session_state["last_click"]:
    folium.Marker(
        [st.session_state["last_click"]["lat"], st.session_state["last_click"]["lng"]],
        popup="📍 Dein Standort (noch nicht gespeichert)",
        icon=folium.Icon(color="red", icon="user")
    ).add_to(m)

st_data = st_folium(m, width=850, height=600)
if st_data["last_clicked"]:
    st.session_state["last_click"] = st_data["last_clicked"]

# ---- 3) Eintragen / Löschen ----
if st.session_state["user"] is not None:
    if st.button("✅ Mich eintragen"):
        if not username:
            st.warning("Ungültiger Benutzername.")
        elif not st.session_state["last_click"]:
            st.warning("Bitte Standort auf der Karte wählen.")
        else:
            lat = st.session_state["last_click"]["lat"]
            lon = st.session_state["last_click"]["lng"]
            personen = [p for p in personen if p["name"] != username]
            personen.append({
                "name": username,
                "role": role,
                "lat": lat,
                "lon": lon,
                "freie_plaetze": freie_plaetze
            })
            save_json(DATA_FILE, personen)
            st.session_state["last_click"] = None
            st.success("Dein Eintrag wurde gespeichert ✅")

# Übersicht Teilnehmer
for p in personen:
    role_icon = "🚗" if "Fahrer" in p["role"] else "🧍"
    color_bg = "#d1f0ff" if "Fahrer" in p["role"] else "#f2f2f2"

    col1, col2 = st.columns([4, 1])
    with col1:
        freie_text = f"<br>Freie Plätze: {p['freie_plaetze']}" if "Fahrer" in p["role"] else ""
        st.markdown(
            f"""
            <div style='background-color:{color_bg}; padding:10px; border-radius:8px; margin-bottom:6px;'>
              <b>{role_icon} {p['name']}</b><br>
              <small>{p['role']}</small><br>
              {freie_text}
            </div>
            """,
            unsafe_allow_html=True
        )
    with col2:
        if st.session_state.get("user") == p["name"]:
            if st.button("🗑️ Löschen", key=f"del_{p['name']}"):
                personen = [x for x in personen if x["name"] != p["name"]]
                for g in gruppen:
                    if p["name"] in g.get("mitglieder", []):
                        g["mitglieder"].remove(p["name"])
                save_json(DATA_FILE, personen)
                save_json(GROUP_FILE, gruppen)
                st.success("Dein Eintrag wurde gelöscht ✅")

st.markdown("---")
st.subheader("👥 Gruppenverwaltung")
if st.session_state["user"] is not None:
    username = st.session_state["user"]

    # Bestehende Gruppen anzeigen
    for g in gruppen:
        members = g.get("mitglieder", [])
        color = g.get("color", "#cccccc")
        cols = st.columns([6, 1, 1])

        with cols[0]:
            st.markdown(
                f"<div style='background-color:{color}; padding:8px; border-radius:6px; margin-bottom:4px;'>"
                f"<b>{g['name']}</b> – Mitglieder: {', '.join(members)}</div>",
                unsafe_allow_html=True
            )

        with cols[1]:
            if username in members:
                if st.button(f"🚪 Verlassen", key=f"leave_{g['name']}"):
                    g["mitglieder"].remove(username)
                    save_json(GROUP_FILE, gruppen)
                    st.success(f"Du hast die Gruppe {g['name']} verlassen.")
            else:
                if st.button(f"➕ Beitreten", key=f"join_{g['name']}"):
                    if any(p["name"] == username for p in personen):
                        g.setdefault("mitglieder", []).append(username)
                        save_json(GROUP_FILE, gruppen)
                        st.success(f"Du bist jetzt Mitglied von {g['name']}.")
                    else:
                        st.warning("Bitte dich zuerst eintragen.")

        with cols[2]:
            if g.get("owner") == username:
                if st.button(f"❌ Löschen", key=f"delgroup_{g['name']}"):
                    gruppen = [x for x in gruppen if x["name"] != g["name"]]
                    save_json(GROUP_FILE, gruppen)
                    st.success(f"Gruppe {g['name']} gelöscht.")

    # Neue Gruppe erstellen
    with st.form("create_group_form"):
        new_name = st.text_input("Name der neuen Gruppe", placeholder="z. B. Team Hamburg")
        submitted = st.form_submit_button("🌈 Gruppe erstellen")

        if submitted:
            if not new_name.strip():
                st.warning("Bitte Gruppennamen eingeben.")
            elif any(g["name"] == new_name for g in gruppen):
                st.warning("Eine Gruppe mit diesem Namen existiert bereits.")
            else:
                if not any(p["name"] == username for p in personen):
                    st.warning("Bitte dich zuerst eintragen.")
                else:
                    new_group = {
                        "name": new_name.strip(),
                        "owner": username,
                        "mitglieder": [username],
                        "color": random_color()
                    }
                    gruppen.append(new_group)
                    save_json(GROUP_FILE, gruppen)
                    st.success(f"Gruppe '{new_name}' erstellt ✅")

# ---- 6) Übersicht Fahrgemeinschaften ----
st.subheader("📊 Übersicht aller Fahrgemeinschaften")
if gruppen:
    gruppen_tabelle = []
    for g in gruppen:
        mitglieder = g.get("mitglieder", [])
        fahrer_daten = [p for p in personen if p["name"] in mitglieder and "Fahrer" in p["role"]]
        fahrer_plaetze = sum(f.get("freie_plaetze", 0) for f in fahrer_daten)
        freie_plaetze_gesamt = max(fahrer_plaetze - (len(mitglieder) - len(fahrer_daten)), 0)
        color = g.get("color", "#cccccc")
        gruppen_tabelle.append({
            "Name": g["name"],
            "Fahrer": g.get("fahrer", "–"),
            "Mitglieder": ", ".join(mitglieder),
            "Anzahl Mitglieder": len(mitglieder),
            "Freie Plätze": freie_plaetze_gesamt,
            "FarbeHTML": f'<div style="background-color:{color}; width:24px; height:24px; border-radius:6px; border:1px solid #333;"></div>'
        })

    st.markdown(
        """
        <style>
        table { width:100%; border-collapse:collapse; }
        th, td { padding:6px 10px; text-align:left; border-bottom:1px solid #ddd; }
        th { background:#f5f5f5; }
        </style>
        """,
        unsafe_allow_html=True
    )

    html_table = "<table><tr><th>Name</th><th>Fahrer</th><th>Mitglieder</th><th>Anzahl Mitglieder</th><th>Freie Plätze</th><th>Farbe</th></tr>"
    for row in gruppen_tabelle:
        html_table += (
            f"<tr><td>{row['Name']}</td>"
            f"<td>{row['Fahrer']}</td>"
            f"<td>{row['Mitglieder']}</td>"
            f"<td>{row['Anzahl Mitglieder']}</td>"
            f"<td>{row['Freie Plätze']}</td>"
            f"<td>{row['FarbeHTML']}</td></tr>"
        )
    html_table += "</table>"
    st.markdown(html_table, unsafe_allow_html=True)
else:
    st.info("Noch keine Gruppen vorhanden.")

# ---- 7) Alles löschen ----

# Nur Admin darf alles löschen
if st.session_state.get("user") == "Admin":
    st.markdown("---")
    st.subheader("⚠️ Alle Daten löschen")

    if st.button("🧹 Alles löschen (Personen & Gruppen)"):
        clear_data()
        st.session_state.clear()
        st.success("Alle Daten wurden gelöscht ✅")
