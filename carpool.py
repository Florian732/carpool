import streamlit as st
import folium
from streamlit_folium import st_folium
from supabase import create_client, Client
import random
from branca.element import MacroElement
from jinja2 import Template

# --- Page Setup ---
st.set_page_config(page_title="🚗 Mitfahrbörse", layout="wide")
st.title("🚗 Mitfahrbörse")

# --- Supabase Verbindung ---
url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]
supabase: Client = create_client(url, key)

service_key = st.secrets.get("supabase_admin", {}).get("service_role_key")
supabase_admin: Client = create_client(url, service_key) if service_key else None

# --- Farben ---
PALETTE = ["#FF0000","#0077FF","#00CC44","#FF9900","#9933FF",
           "#00CED1","#FF1493","#8B4513","#FFD700","#008B8B"]
def random_color():
    return random.choice(PALETTE)

# --- Session-State laden ---
if "user" not in st.session_state:
    st.session_state["user"] = None
if "personen" not in st.session_state:
    st.session_state["personen"] = supabase.table("personen").select("*").execute().data
if "gruppen" not in st.session_state:
    st.session_state["gruppen"] = supabase.table("gruppen").select("*").execute().data
if "last_click" not in st.session_state:
    st.session_state["last_click"] = None

# --- Anmeldung ---
st.sidebar.header("🔐 Anmeldung")
if st.session_state["user"] is None:
    temp_name = st.sidebar.text_input("Dein Name", placeholder="Vorname und Nachname")
    if st.sidebar.button("Anmelden"):
        if temp_name.strip():
            st.session_state["user"] = temp_name.strip()
            st.sidebar.success(f"Angemeldet als: {st.session_state['user']}")
        else:
            st.sidebar.warning("Bitte Namen eingeben.")
else:
    st.sidebar.write(f"👋 Angemeldet als **{st.session_state['user']}**")
    if st.sidebar.button("Abmelden"):
        st.session_state["user"] = None
        st.experimental_rerun()  # hier nur für Logout nötig
username = st.session_state.get("user")

# --- Teilnahmeformular ---
st.subheader("👤 Deine Teilnahme")
if username:
    existing_person = next((p for p in st.session_state["personen"] if p["name"] == username), None)
    role_default = existing_person["role"] if existing_person else "Mitfahrer (suche Platz)"
    role = st.radio(
        "Ich bin …",
        ["Fahrer (biete Plätze an)", "Mitfahrer (suche Platz)"],
        index=0 if "Fahrer" in role_default else 1
    )
    if "Fahrer" in role:
        freie_plaetze = st.number_input(
            "Wie viele Plätze hast du frei?",
            min_value=0, max_value=8,
            value=existing_person["freie_plaetze"] if existing_person else 3
        )
    else:
        freie_plaetze = 0
else:
    st.info("Bitte melde dich links an.")

st.info("Klicke auf die Karte, um deinen Standort zu wählen.")

# --- Map ---
m = folium.Map(location=[53.6, 9.9], zoom_start=8)

for p in st.session_state["personen"]:
    color = "green" if "Fahrer" in p["role"] else "blue"
    folium.Marker(
        [p["lat"], p["lon"]],
        popup=f"{p['name']} ({p['role']})",
        icon=folium.Icon(color=color)
    ).add_to(m)

if st.session_state["last_click"]:
    folium.Marker(
        [st.session_state["last_click"]["lat"], st.session_state["last_click"]["lng"]],
        popup="📍 Dein Standort",
        icon=folium.Icon(color="red", icon="user")
    ).add_to(m)

# Gruppenlinien
legende_html = "<b>🎨 Fahrgemeinschaften</b><br>"
for g in st.session_state["gruppen"]:
    color = g.get("color", random_color())
    members = [p for p in st.session_state["personen"] if p["name"] in g["mitglieder"]]
    coords = [(p["lat"], p["lon"]) for p in members]
    if len(coords) > 1:
        folium.PolyLine(coords, color=color, weight=5, opacity=0.8).add_to(m)
        legende_html += f'<i style="background:{color};width:18px;height:18px;display:inline-block;margin-right:5px;"></i>{g["name"]}<br>'

if st.session_state["gruppen"]:
    legend = MacroElement()
    legend._template = Template(f"""
        <div style="position: fixed; bottom: 30px; right: 30px; background-color: white;
                    padding: 10px; border-radius: 10px; border: 1px solid grey;">
            {legende_html}
        </div>
    """)
    m.get_root().add_child(legend)

map_data = st_folium(m, width=850, height=600)
if map_data["last_clicked"]:
    st.session_state["last_click"] = map_data["last_clicked"]

# --- Eintragen ---
if username and st.button("✅ Mich eintragen"):
    if not st.session_state["last_click"]:
        st.warning("Bitte erst auf die Karte klicken!")
    else:
        supabase.table("personen").upsert({
            "name": username,
            "role": role,
            "lat": st.session_state["last_click"]["lat"],
            "lon": st.session_state["last_click"]["lng"],
            "freie_plaetze": freie_plaetze
        }).execute()
        # Direkt im Session-State spiegeln
        existing_person_data = next((p for p in st.session_state["personen"] if p["name"] == username), None)
        person_data = {
            "name": username,
            "role": role,
            "lat": st.session_state["last_click"]["lat"],
            "lon": st.session_state["last_click"]["lng"],
            "freie_plaetze": freie_plaetze
        }
        if existing_person_data:
            idx = st.session_state["personen"].index(existing_person_data)
            st.session_state["personen"][idx] = person_data
        else:
            st.session_state["personen"].append(person_data)
        st.session_state["last_click"] = None

# --- Personenübersicht ---
st.subheader("👥 Übersicht Teilnehmer")
for p in st.session_state["personen"]:
    role_icon = "🚗" if "Fahrer" in p["role"] else "🧍"
    color_bg = "#d1f0ff" if "Fahrer" in p["role"] else "#f2f2f2"
    freie_text = f"<br>Freie Plätze: {p['freie_plaetze']}" if "Fahrer" in p["role"] else ""

    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(
            f"<div style='background-color:{color_bg}; padding:10px; border-radius:8px; margin-bottom:6px;'>"
            f"<b>{role_icon} {p['name']}</b><br><small>{p['role']}</small>{freie_text}</div>",
            unsafe_allow_html=True
        )
    with col2:
        if username == p["name"]:
            if st.button("🗑️ Löschen", key=f"del_{p['name']}"):
                supabase.table("personen").delete().eq("name", username).execute()
                st.session_state["personen"].remove(p)

# --- Gruppenverwaltung ---
st.subheader("👥 Gruppenverwaltung")
if username:
    for g in st.session_state["gruppen"][:]:  # copy für sicheres Entfernen
        members = g["mitglieder"]
        color = g.get("color", "#cccccc")
        freie_plaetze = sum(p["freie_plaetze"] for p in st.session_state["personen"]
                            if p["name"] in members and "Fahrer" in p["role"])
        freie_text = f" – Freie Plätze: {freie_plaetze}" if freie_plaetze else ""

        cols = st.columns([6,1,1])
        with cols[0]:
            st.markdown(
                f"<div style='background-color:{color}; padding:8px; border-radius:6px;'>"
                f"<b>{g['name']}</b> – Mitglieder: {', '.join(members)}{freie_text}</div>",
                unsafe_allow_html=True
            )
        with cols[1]:
            if username in members:
                if st.button("🚪 Verlassen", key=f"leave_{g['name']}"):
                    members.remove(username)
                    supabase.table("gruppen").update({"mitglieder": members}).eq("name", g["name"]).execute()
                    g["mitglieder"] = members
            else:
                if st.button("➕ Beitreten", key=f"join_{g['name']}"):
                    members.append(username)
                    supabase.table("gruppen").update({"mitglieder": members}).eq("name", g["name"]).execute()
                    g["mitglieder"] = members
        with cols[2]:
            if g.get("owner") == username:
                if st.button("❌ Löschen", key=f"delgroup_{g['name']}"):
                    supabase.table("gruppen").delete().eq("name", g["name"]).execute()
                    st.session_state["gruppen"].remove(g)

    # Neue Gruppe
    with st.form("create_group_form"):
        new_name = st.text_input("Name der neuen Gruppe", placeholder="z. B. Team Hamburg")
        submitted = st.form_submit_button("🌈 Gruppe erstellen")
        if submitted:
            if new_name.strip() and all(g["name"] != new_name for g in st.session_state["gruppen"]):
                new_group = {
                    "name": new_name.strip(),
                    "owner": username,
                    "mitglieder": [username],
                    "color": random_color()
                }
                supabase.table("gruppen").insert(new_group).execute()
                st.session_state["gruppen"].append(new_group)
            else:
                st.warning("Ungültiger Name oder Gruppe existiert bereits.")

# --- Admin: Alles löschen ---
if username == "Admin" and supabase_admin:
    if st.button("🧹 Alles löschen (Personen & Gruppen)"):
        supabase_admin.table("personen").delete().neq("name", "").execute()
        supabase_admin.table("gruppen").delete().neq("name", "").execute()
        st.session_state["personen"] = []
        st.session_state["gruppen"] = []
