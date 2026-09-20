import hashlib
import hmac
import io
import json
from urllib.parse import quote
from urllib.request import Request, urlopen

import streamlit as st
import pandas as pd
import folium
import plotly.graph_objects as go
from streamlit_folium import st_folium

from optimizer import (
    find_best_warehouses,
    calculate_baseline,
    calculate_average_travel_time,
)


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="GRIDPOINT // Logistics Intelligence",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# SIMPLE DEMO AUTHENTICATION
# ============================================================
# Hackathon/demo authentication only. For production, use a proper
# authentication provider and secret storage.
AUTH_EMAIL = "kiransrinivas.cs25@bmsce.ac.in"
AUTH_PASSWORD_HASH = hashlib.sha256("HAIL HYDRA".encode("utf-8")).hexdigest()

def verify_credentials(email, password):
    return (
        hmac.compare_digest(email.strip().lower(), AUTH_EMAIL.lower())
        and hmac.compare_digest(
            hashlib.sha256(password.encode("utf-8")).hexdigest(),
            AUTH_PASSWORD_HASH,
        )
    )


# ============================================================
# SESSION STATE
# ============================================================

RESULT_KEYS = [
    "warehouses",
    "assignments",
    "total_cost",
    "total_distance",
    "weighted_distance",
    "baseline_cost",
    "baseline_lat",
    "baseline_lon",
    "baseline_distance",
    "average_time",
    "baseline_time",
    "optimization_failed",
]


def clear_results():
    for key in RESULT_KEYS:
        st.session_state.pop(key, None)


def load_data(data):
    st.session_state["data"] = data.copy()
    clear_results()


def get_signature(uploaded_file):
    if uploaded_file is None:
        return None

    return hashlib.md5(
        uploaded_file.getvalue()
    ).hexdigest()


@st.cache_data(ttl=3600, show_spinner=False)
def get_road_route(lat1, lon1, lat2, lon2):
    """Return a road-following route as [[lat, lon], ...].

    This is used only for the visual map connection. GRIDPOINT's existing
    optimizer, geographic distance calculation, cost calculation, capacity
    logic and delivery-radius logic are not changed.
    """
    try:
        coordinates = (
            f"{float(lon1)},{float(lat1)};"
            f"{float(lon2)},{float(lat2)}"
        )

        url = (
            "https://router.project-osrm.org/route/v1/driving/"
            f"{quote(coordinates, safe=',;')}"
            "?overview=full&geometries=geojson&steps=false"
        )

        request = Request(
            url,
            headers={
                "User-Agent": "GRIDPOINT-Hackathon/1.0"
            },
        )

        with urlopen(request, timeout=6) as response:
            payload = json.loads(
                response.read().decode("utf-8")
            )

        routes = payload.get("routes", [])
        if not routes:
            return None

        geometry = routes[0].get("geometry", {})
        route_coordinates = geometry.get("coordinates", [])

        if len(route_coordinates) < 2:
            return None

        return [
            [float(point[1]), float(point[0])]
            for point in route_coordinates
        ]

    except Exception:
        return None


# ============================================================
# GAMING HUD CSS
# ============================================================

st.html("""
<style>

@import url(
'https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700;800;900&family=Rajdhani:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap'
);

/* ==========================================================
   GLOBAL
   ========================================================== */

html,
body,
.stApp,
[data-testid="stAppViewContainer"] {

    background: #060613 !important;

    color: #e8f2ff !important;

}

* {
    box-sizing: border-box;
}

body {
    font-family:
        "Rajdhani",
        sans-serif;
}

.block-container {

    position: relative;

    z-index: 1;

    max-width: 1750px !important;

    padding-top: 8px !important;

    padding-left: 14px !important;

    padding-right: 14px !important;

    padding-bottom: 35px !important;

}

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

header {
    background: transparent !important;
}


/* ==========================================================
   ANIMATED GAMING BACKGROUND
   ========================================================== */

.bg-layer {

    position: fixed;

    inset: 0;

    z-index: -1;

    overflow: hidden;

    pointer-events: none;

    background:
        radial-gradient(
            circle at 10% 0%,
            rgba(255, 0, 170, .08),
            transparent 26%
        ),
        radial-gradient(
            circle at 90% 10%,
            rgba(5, 217, 232, .08),
            transparent 26%
        ),
        radial-gradient(
            circle at 50% 100%,
            rgba(123, 47, 247, .10),
            transparent 40%
        ),
        #060613;

}

.bg-hexgrid {

    position: absolute;

    inset: -80px;

    background-image:
        repeating-linear-gradient(
            60deg,
            rgba(5, 217, 232, .05) 0px,
            rgba(5, 217, 232, .05) 1px,
            transparent 1px,
            transparent 46px
        ),
        repeating-linear-gradient(
            -60deg,
            rgba(255, 42, 109, .05) 0px,
            rgba(255, 42, 109, .05) 1px,
            transparent 1px,
            transparent 46px
        ),
        repeating-linear-gradient(
            0deg,
            rgba(123, 47, 247, .04) 0px,
            rgba(123, 47, 247, .04) 1px,
            transparent 1px,
            transparent 46px
        );

    animation: hexDrift 34s linear infinite;

    mask-image:
        radial-gradient(
            ellipse at 50% 30%,
            rgba(0,0,0,.9),
            transparent 80%
        );

}

@keyframes hexDrift {

    0% {
        transform: translate(0, 0);
    }

    100% {
        transform: translate(46px, 80px);
    }

}

.bg-sweep {

    position: absolute;

    top: -50%;

    left: -20%;

    width: 45%;

    height: 220%;

    background:
        linear-gradient(
            100deg,
            transparent,
            rgba(5, 217, 232, .05) 45%,
            rgba(255, 42, 109, .06) 50%,
            transparent 60%
        );

    transform: rotate(12deg);

    animation: sweepMove 11s ease-in-out infinite;

}

@keyframes sweepMove {

    0% {
        left: -40%;
    }

    50% {
        left: 110%;
    }

    100% {
        left: 110%;
    }

}

.bg-blob {

    position: absolute;

    border-radius: 50%;

    filter: blur(70px);

    will-change: transform;

}

.bg-blob-magenta {

    width: 460px;

    height: 460px;

    top: -140px;

    left: -110px;

    background:
        radial-gradient(
            circle,
            rgba(255, 42, 109, .18),
            transparent 70%
        );

    animation: blobFloatA 22s ease-in-out infinite;

}

.bg-blob-cyan {

    width: 500px;

    height: 500px;

    top: 32%;

    right: -180px;

    background:
        radial-gradient(
            circle,
            rgba(5, 217, 232, .16),
            transparent 70%
        );

    animation: blobFloatB 28s ease-in-out infinite;

}

.bg-blob-purple {

    width: 420px;

    height: 420px;

    bottom: -150px;

    left: 28%;

    background:
        radial-gradient(
            circle,
            rgba(123, 47, 247, .16),
            transparent 70%
        );

    animation: blobFloatC 32s ease-in-out infinite;

}

@keyframes blobFloatA {

    0%, 100% {
        transform: translate(0, 0) scale(1);
    }

    50% {
        transform: translate(70px, 50px) scale(1.14);
    }

}

@keyframes blobFloatB {

    0%, 100% {
        transform: translate(0, 0) scale(1);
    }

    50% {
        transform: translate(-90px, -40px) scale(1.1);
    }

}

@keyframes blobFloatC {

    0%, 100% {
        transform: translate(0, 0) scale(1);
    }

    50% {
        transform: translate(50px, -70px) scale(1.16);
    }

}

.bg-particles {

    position: absolute;

    inset: 0;

}

.bg-particle {

    position: absolute;

    bottom: -10px;

    width: 3px;

    height: 3px;

    border-radius: 50%;

    background: rgba(5, 217, 232, .8);

    box-shadow: 0 0 8px rgba(5, 217, 232, .8);

    animation-name: particleRise;

    animation-timing-function: linear;

    animation-iteration-count: infinite;

}

.bg-particle.magenta {

    background: rgba(255, 42, 109, .8);

    box-shadow: 0 0 8px rgba(255, 42, 109, .8);

}

@keyframes particleRise {

    0% {
        transform: translateY(0) translateX(0);
        opacity: 0;
    }

    8% {
        opacity: .8;
    }

    92% {
        opacity: .3;
    }

    100% {
        transform: translateY(-760px) translateX(26px);
        opacity: 0;
    }

}


/* ==========================================================
   SHARED HUD PANEL SHAPE
   ========================================================== */

.panel,
.hero,
.telemetry,
.result,
.warehouse,
.stat,
.assignment,
.map-box,
.control-box {

    clip-path: polygon(
        12px 0,
        100% 0,
        100% calc(100% - 12px),
        calc(100% - 12px) 100%,
        0 100%,
        0 12px
    );

}


/* ==========================================================
   TOP BAR
   ========================================================== */

.nav {

    height: 56px;

    display: flex;

    align-items: center;

    justify-content: space-between;

    padding: 0 10px;

    border-bottom: 1px solid rgba(5, 217, 232, .18);

    margin-bottom: 10px;

    background:
        linear-gradient(
            90deg,
            rgba(255,42,109,.05),
            transparent 30%,
            transparent 70%,
            rgba(5,217,232,.05)
        );

}

.brand {

    display: flex;

    align-items: center;

    gap: 10px;

}

.brand-mark {

    width: 34px;

    height: 34px;

    display: flex;

    align-items: center;

    justify-content: center;

    clip-path: polygon(
        20% 0, 100% 0, 100% 80%, 80% 100%, 0 100%, 0 20%
    );

    border: 1px solid rgba(5, 217, 232, .7);

    background:
        linear-gradient(
            135deg,
            rgba(255,42,109,.22),
            rgba(5,217,232,.20)
        );

    color: #05d9e8;

    font-family: "Orbitron";

    font-weight: 800;

    font-size: 16px;

    box-shadow: 0 0 18px rgba(5,217,232,.20);

    animation: markPulse 3.2s ease-in-out infinite;

}

@keyframes markPulse {

    0%, 100% {
        box-shadow: 0 0 12px rgba(5,217,232,.18);
        border-color: rgba(5, 217, 232, .6);
    }

    50% {
        box-shadow: 0 0 26px rgba(255,42,109,.35);
        border-color: rgba(255, 42, 109, .7);
    }

}

.brand-name {

    color: #f4f9ff;

    font-family: "Orbitron";

    font-size: 15px;

    font-weight: 800;

    letter-spacing: 2px;

    text-shadow: 0 0 16px rgba(5,217,232,.4);

}

.brand-sub {

    color: #6b7a99;

    font-family: "IBM Plex Mono";

    font-size: 8px;

    margin-left: 8px;

    letter-spacing: .8px;

}

.nav-center {

    color: #7f8fb3;

    font-family: "Orbitron";

    font-size: 8px;

    letter-spacing: 2px;

}

.live {

    color: #39ff8c;

    background: rgba(57,255,140,.06);

    border: 1px solid rgba(57,255,140,.30);

    padding: 7px 12px;

    font-family: "Orbitron";

    font-size: 8px;

    font-weight: 700;

    letter-spacing: 1px;

    clip-path: polygon(
        10px 0, 100% 0, 100% 100%, 0 100%, 0 10px
    );

}

.live-dot {

    display: inline-block;

    width: 6px;

    height: 6px;

    border-radius: 50%;

    background: #39ff8c;

    box-shadow: 0 0 10px #39ff8c;

    margin-right: 6px;

    animation: dotPulse 1.3s ease-in-out infinite;

}

@keyframes dotPulse {

    0%, 100% {
        opacity: 1;
        box-shadow: 0 0 10px #39ff8c;
    }

    50% {
        opacity: .45;
        box-shadow: 0 0 3px #39ff8c;
    }

}


/* ==========================================================
   PANEL
   ========================================================== */

.panel {

    position: relative;

    border: 1px solid rgba(5,217,232,.16);

    background:
        linear-gradient(
            180deg,
            rgba(15,15,32,.96),
            rgba(8,8,20,.98)
        );

    padding: 13px;

    height: 100%;

    transition: border-color .25s ease, box-shadow .25s ease;

}

.panel:hover {

    border-color: rgba(255,42,109,.45);

    box-shadow: 0 0 24px rgba(255,42,109,.10);

}

.panel-header {

    display: flex;

    align-items: center;

    justify-content: space-between;

    margin-bottom: 9px;

}

.panel-title {

    color: #eaf2ff;

    font-family: "Orbitron";

    font-size: 9px;

    font-weight: 700;

    letter-spacing: 1.4px;

}

.panel-tag {

    color: #05d9e8;

    border: 1px solid rgba(5,217,232,.30);

    background: rgba(5,217,232,.06);

    padding: 3px 8px;

    font-family: "Orbitron";

    font-size: 7px;

    letter-spacing: 1px;

}

.line {

    height: 2px;

    background:
        linear-gradient(
            90deg,
            #ff2a6d,
            #05d9e8 45%,
            transparent
        );

    margin-bottom: 10px;

}


/* ==========================================================
   HERO
   ========================================================== */

.hero {

    position: relative;

    overflow: hidden;

    padding: 22px;

    margin-bottom: 8px;

    border: 1px solid rgba(5,217,232,.20);

    background:
        linear-gradient(
            120deg,
            rgba(20,12,35,.98),
            rgba(8,8,20,.98)
        );

    animation: heroBorderGlow 5s ease-in-out infinite;

}

@keyframes heroBorderGlow {

    0%, 100% {
        border-color: rgba(5,217,232,.20);
        box-shadow: 0 0 0 rgba(255,42,109,0);
    }

    50% {
        border-color: rgba(255,42,109,.40);
        box-shadow: 0 0 34px rgba(255,42,109,.08);
    }

}

.hero::after {

    content: "";

    position: absolute;

    width: 380px;

    height: 380px;

    right: -170px;

    top: -230px;

    border-radius: 50%;

    background:
        radial-gradient(
            circle,
            rgba(5,217,232,.20),
            transparent 65%
        );

    animation: blobFloatA 18s ease-in-out infinite;

}

.hero-kicker {

    color: #ff2a6d;

    font-family: "Orbitron";

    font-size: 8px;

    font-weight: 700;

    letter-spacing: 2.4px;

    text-shadow: 0 0 12px rgba(255,42,109,.5);

}

.hero-title {

    position: relative;

    z-index: 2;

    margin-top: 9px;

    color: #f4f9ff;

    font-family: "Orbitron";

    font-size: 29px;

    line-height: 1.15;

    font-weight: 700;

    letter-spacing: -.5px;

    animation: titleFlicker 7s linear infinite;

}

@keyframes titleFlicker {

    0%, 96%, 100% {
        opacity: 1;
    }

    97% {
        opacity: .82;
    }

    98% {
        opacity: 1;
    }

}

.hero-title span {

    color: #05d9e8;

    text-shadow: 0 0 20px rgba(5,217,232,.55);

}

.hero-copy {

    position: relative;

    z-index: 2;

    max-width: 690px;

    margin-top: 9px;

    color: #8b98b8;

    font-family: "IBM Plex Mono";

    font-size: 8px;

    line-height: 1.7;

}


/* ==========================================================
   SMALL STAT CARDS
   ========================================================== */

.stats {

    display: grid;

    grid-template-columns: repeat(3, 1fr);

    gap: 6px;

    margin-bottom: 8px;

}

.stat {

    padding: 10px;

    border: 1px solid rgba(5,217,232,.14);

    background: rgba(5,217,232,.03);

    transition: transform .2s ease, border-color .2s ease;

}

.stat:hover {

    transform: translateY(-2px);

    border-color: rgba(255,42,109,.4);

}

.stat-label {

    color: #6b7a99;

    font-family: "Orbitron";

    font-size: 7px;

    letter-spacing: 1px;

}

.stat-value {

    margin-top: 5px;

    color: #eaf2ff;

    font-family: "IBM Plex Mono";

    font-size: 18px;

    font-weight: 700;

}

.cyan {
    color: #05d9e8 !important;
    text-shadow: 0 0 10px rgba(5,217,232,.4);
}

.blue {
    color: #4d8dff !important;
    text-shadow: 0 0 10px rgba(77,141,255,.4);
}

.green {
    color: #39ff8c !important;
    text-shadow: 0 0 10px rgba(57,255,140,.4);
}

.orange {
    color: #ffb800 !important;
    text-shadow: 0 0 10px rgba(255,184,0,.4);
}

.pink {
    color: #ff2a6d !important;
    text-shadow: 0 0 10px rgba(255,42,109,.4);
}

.purple {
    color: #b967ff !important;
    text-shadow: 0 0 10px rgba(185,103,255,.4);
}


/* ==========================================================
   MAP
   ========================================================== */

.map-box {

    position: relative;

    border: 1px solid rgba(5,217,232,.22);

    padding: 4px;

    background: #05050f;

    animation: mapBorderGlow 4.5s ease-in-out infinite;

}

@keyframes mapBorderGlow {

    0%, 100% {
        border-color: rgba(5,217,232,.22);
        box-shadow: 0 0 0 rgba(5,217,232,0);
    }

    50% {
        border-color: rgba(255,42,109,.5);
        box-shadow: 0 0 30px rgba(255,42,109,.12);
    }

}


/* ==========================================================
   RIGHT TELEMETRY
   ========================================================== */

.telemetry {

    padding: 13px;

    margin-bottom: 7px;

    border: 1px solid rgba(123,47,247,.20);

    background:
        linear-gradient(
            145deg,
            rgba(16,14,30,.98),
            rgba(8,8,18,.98)
        );

    transition: border-color .25s ease, transform .2s ease;

}

.telemetry:hover {

    border-color: rgba(185,103,255,.5);

    transform: translateY(-2px);

}

.telemetry-label {

    color: #7f8fb3;

    font-family: "Orbitron";

    font-size: 7px;

    font-weight: 700;

    letter-spacing: 1.2px;

}

.telemetry-number {

    color: #f4f9ff;

    font-family: "IBM Plex Mono";

    font-size: 26px;

    font-weight: 700;

    margin-top: 5px;

}

.telemetry-number small {

    color: #6b7a99;

    font-size: 8px;

    font-weight: 400;

}

.telemetry-note {

    color: #6b7a99;

    font-family: "IBM Plex Mono";

    font-size: 7px;

    margin-top: 4px;

}


/* ==========================================================
   COMPARISON
   ========================================================== */

.compare {

    display: grid;

    grid-template-columns: 1fr 1fr;

    gap: 1px;

    margin-top: 8px;

    background: rgba(5,217,232,.10);

}

.compare-cell {

    background: #0a0a18;

    padding: 8px;

}

.compare-label {

    color: #6b7a99;

    font-family: "Orbitron";

    font-size: 6px;

    letter-spacing: .8px;

}

.compare-value {

    color: #eaf2ff;

    font-family: "IBM Plex Mono";

    font-size: 12px;

    font-weight: 700;

    margin-top: 4px;

}


/* ==========================================================
   ASSIGNMENT
   ========================================================== */

.assignment {

    padding: 8px;

    margin-top: 5px;

    border: 1px solid rgba(255,42,109,.14);

    background: rgba(255,42,109,.02);

    transition: border-color .2s ease;

}

.assignment:hover {

    border-color: rgba(255,42,109,.5);

}

.assignment-top {

    display: flex;

    justify-content: space-between;

    gap: 5px;

}

.assignment-name {

    color: #d7deee;

    font-family: "IBM Plex Mono";

    font-size: 7px;

    overflow: hidden;

    text-overflow: ellipsis;

    white-space: nowrap;

}

.assignment-value {

    color: #ff2a6d;

    font-family: "IBM Plex Mono";

    font-size: 7px;

    font-weight: 700;

}

.progress {

    height: 5px;

    margin-top: 7px;

    background: #131226;

    overflow: hidden;

    clip-path: polygon(4px 0, 100% 0, 100% 100%, 0 100%, 0 4px);

}

.progress-fill {

    height: 100%;

    background:
        linear-gradient(
            90deg,
            #05d9e8,
            #ff2a6d
        );

    background-size: 200% 100%;

    animation: progressShimmer 2.6s linear infinite;

}

@keyframes progressShimmer {

    0% {
        background-position: 0% 0;
    }

    100% {
        background-position: 200% 0;
    }

}


/* ==========================================================
   CONTROL SECTION
   ========================================================== */

.control-box {

    padding: 10px;

    margin-top: 7px;

    border: 1px solid rgba(5,217,232,.14);

    background: rgba(5,217,232,.025);

}

.control-label {

    color: #05d9e8;

    font-family: "Orbitron";

    font-size: 7px;

    font-weight: 700;

    letter-spacing: 1.4px;

    margin-bottom: 6px;

}


/* ==========================================================
   RESULT CARDS
   ========================================================== */

.result-grid {

    display: grid;

    grid-template-columns: repeat(4, 1fr);

    gap: 7px;

}

.result {

    padding: 13px;

    border: 1px solid rgba(5,217,232,.16);

    background:
        linear-gradient(
            145deg,
            rgba(15,15,30,.97),
            rgba(8,8,18,.98)
        );

    transition: transform .2s ease, border-color .2s ease;

}

.result:hover {

    transform: translateY(-3px);

    border-color: rgba(255,42,109,.45);

    box-shadow: 0 0 20px rgba(255,42,109,.10);

}

.result-label {

    color: #7f8fb3;

    font-family: "Orbitron";

    font-size: 7px;

    letter-spacing: .9px;

}

.result-value {

    color: #f4f9ff;

    font-family: "IBM Plex Mono";

    font-size: 20px;

    font-weight: 700;

    margin-top: 5px;

}


/* ==========================================================
   WAREHOUSE CARDS
   ========================================================== */

.warehouse-grid {

    display: grid;

    grid-template-columns: repeat(4, 1fr);

    gap: 7px;

}

.warehouse {

    position: relative;

    padding: 13px;

    border: 1px solid rgba(123,47,247,.20);

    background:
        linear-gradient(
            145deg,
            rgba(16,14,30,.98),
            rgba(8,8,18,.98)
        );

    overflow: hidden;

    transition: transform .2s ease, border-color .2s ease;

}

.warehouse:hover {

    transform: translateY(-3px);

    border-color: rgba(185,103,255,.5);

    box-shadow: 0 0 20px rgba(123,47,247,.14);

}

.warehouse::before {

    content: "";

    position: absolute;

    left: 0;

    top: 0;

    bottom: 0;

    width: 3px;

    background: linear-gradient(#05d9e8, #ff2a6d);

}

.warehouse-id {

    color: #7f8fb3;

    font-family: "Orbitron";

    font-size: 7px;

    letter-spacing: 1.2px;

}

.warehouse-name {

    color: #eaf2ff;

    font-family: "Orbitron";

    font-size: 11px;

    font-weight: 700;

    margin-top: 5px;

}

.warehouse-meta {

    color: #6b7a99;

    font-family: "IBM Plex Mono";

    font-size: 7px;

    margin-top: 5px;

}


/* ==========================================================
   SECTION TITLE
   ========================================================== */

.section-kicker {

    color: #ff2a6d;

    font-family: "Orbitron";

    font-size: 7px;

    font-weight: 700;

    letter-spacing: 1.6px;

    margin-top: 20px;

}

.section-heading {

    color: #eaf2ff;

    font-family: "Orbitron";

    font-size: 16px;

    font-weight: 700;

    margin-top: 4px;

}

.section-rule {

    height: 2px;

    margin: 8px 0;

    background:
        linear-gradient(
            90deg,
            #05d9e8,
            #ff2a6d 40%,
            transparent
        );

}


/* ==========================================================
   STREAMLIT CONTROLS
   ========================================================== */

.stButton > button {

    min-height: 42px !important;

    clip-path: polygon(
        10px 0, 100% 0, 100% calc(100% - 10px), calc(100% - 10px) 100%, 0 100%, 0 10px
    ) !important;

    border-radius: 0 !important;

    border: 1px solid rgba(5,217,232,.5) !important;

    background:
        linear-gradient(
            110deg,
            #ff2a6d,
            #b967ff 50%,
            #05d9e8
        ) !important;

    background-size: 220% 100% !important;

    color: #060613 !important;

    font-family: "Orbitron" !important;

    font-size: 8px !important;

    font-weight: 800 !important;

    letter-spacing: 1px;

    box-shadow: 0 8px 25px rgba(255,42,109,.12) !important;

    transition: box-shadow .2s ease, transform .15s ease,
        background-position .5s ease !important;

}

.stButton > button:hover {

    border-color: #05d9e8 !important;

    box-shadow: 0 0 26px rgba(5,217,232,.35) !important;

    transform: translateY(-1px);

    background-position: 100% 0 !important;

}

.stNumberInput input {

    border-radius: 0 !important;

    background: #0a0a18 !important;

    color: #eaf2ff !important;

    font-family: "IBM Plex Mono" !important;

    font-size: 9px !important;

    border-color: rgba(5,217,232,.25) !important;

}

[data-testid="stFileUploader"] {

    border: 1px dashed rgba(5,217,232,.35);

    border-radius: 0;

    background: rgba(5,217,232,.03);

}

[data-baseweb="select"] > div {

    background: #0a0a18 !important;

    border-radius: 0 !important;

    border-color: rgba(5,217,232,.25) !important;

}

.stCheckbox label {

    font-family: "IBM Plex Mono" !important;

    font-size: 8px !important;

}

[data-testid="stDataFrame"] {

    border-radius: 0;

    border: 1px solid rgba(5,217,232,.16);

}

.stRadio label {

    font-family: "Orbitron" !important;

    font-size: 8px !important;

}


/* ==========================================================
   FINAL UX POLISH
   ========================================================== */

.dashboard-spacer {
    height: 24px;
}

.workflow-section {
    margin-top: 42px;
    padding: 24px 0 10px 0;
}

.workflow-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin-top: 18px;
}

.workflow-card {
    position: relative;
    min-height: 165px;
    padding: 18px;
    border: 1px solid rgba(5,217,232,.15);
    background: linear-gradient(145deg, rgba(15,15,30,.98), rgba(8,8,18,.98));
    overflow: hidden;
}

.workflow-card::after {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 2px;
    background: linear-gradient(90deg, #05d9e8, #ff2a6d);
    opacity: .8;
}

.workflow-number {
    color: #ff2a6d;
    font-family: "Orbitron";
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.4px;
}

.workflow-title {
    color: #eef5ff;
    font-family: "Orbitron";
    font-size: 11px;
    font-weight: 700;
    margin-top: 14px;
}

.workflow-copy {
    color: #8492ad;
    font-family: "IBM Plex Mono";
    font-size: 8px;
    line-height: 1.75;
    margin-top: 10px;
}

.result-hero {
    margin-top: 22px;
    padding: 24px;
    border: 1px solid rgba(57,255,140,.18);
    background: linear-gradient(135deg, rgba(57,255,140,.055), rgba(5,217,232,.025) 55%, rgba(255,42,109,.035));
    box-shadow: inset 0 0 40px rgba(5,217,232,.025);
}

.result-hero-grid {
    display: grid;
    grid-template-columns: 1.15fr 1fr 1fr;
    gap: 18px;
    align-items: stretch;
}

.result-hero-label {
    color: #71809e;
    font-family: "Orbitron";
    font-size: 7px;
    font-weight: 700;
    letter-spacing: 1.2px;
}

.result-hero-value {
    color: #39ff8c;
    font-family: "IBM Plex Mono";
    font-size: 28px;
    font-weight: 700;
    margin-top: 8px;
}

.result-hero-note {
    color: #8492ad;
    font-family: "IBM Plex Mono";
    font-size: 8px;
    line-height: 1.65;
    margin-top: 7px;
}

.result-hero-cell {
    padding: 16px;
    border-left: 1px solid rgba(5,217,232,.12);
}

.result-hero-cell:first-child {
    border-left: 0;
}

.assumption-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-top: 16px;
}

.assumption-card {
    min-height: 135px;
    padding: 17px;
    border: 1px solid rgba(5,217,232,.12);
    background: rgba(5,217,232,.018);
}

.assumption-title {
    color: #05d9e8;
    font-family: "Orbitron";
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 1px;
}

.assumption-copy {
    color: #7f8fb3;
    font-family: "IBM Plex Mono";
    font-size: 8px;
    line-height: 1.75;
    margin-top: 9px;
}

.demo-note {
    margin-top: 12px;
    padding: 13px 15px;
    border-left: 3px solid #05d9e8;
    background: rgba(5,217,232,.035);
    color: #8998b5;
    font-family: "IBM Plex Mono";
    font-size: 8px;
    line-height: 1.75;
}

.error-guide {
    margin-top: 12px;
    padding: 17px;
    border: 1px solid rgba(255,42,109,.2);
    background: rgba(255,42,109,.035);
    color: #9aa8c2;
    font-family: "IBM Plex Mono";
    font-size: 8px;
    line-height: 1.8;
}

.error-guide strong {
    color: #ff6e9e;
}

/* Give the dashboard more breathing room instead of compressing every block. */
[data-testid="stHorizontalBlock"] {
    gap: 1.25rem !important;
}

.stButton {
    margin-top: 5px;
}

.result {
    min-height: 108px;
    padding: 19px;
}

.warehouse {
    min-height: 165px;
    padding: 19px;
}

.section-kicker {
    margin-top: 38px;
}

.section-heading {
    margin-top: 8px;
}

.section-rule {
    margin: 12px 0 18px 0;
}

.footer {
    margin-top: 70px;
    padding-bottom: 28px;
}

@media(max-width: 1100px) {
    .workflow-grid {
        grid-template-columns: repeat(2, 1fr);
    }

    .result-hero-grid {
        grid-template-columns: 1fr;
    }

    .result-hero-cell {
        border-left: 0;
        border-top: 1px solid rgba(5,217,232,.12);
    }

    .result-hero-cell:first-child {
        border-top: 0;
    }
}

@media(max-width: 700px) {
    .workflow-grid,
    .assumption-grid {
        grid-template-columns: 1fr;
    }
}


/* ==========================================================
   FOOTER
   ========================================================== */

.footer {

    display: flex;

    justify-content: space-between;

    margin-top: 20px;

    padding-top: 12px;

    border-top: 1px solid rgba(5,217,232,.14);

    color: #6b7a99;

    font-family: "Orbitron";

    font-size: 7px;

    letter-spacing: 1px;

}


/* ==========================================================
   MOBILE / RESPONSIVE
   ========================================================== */

@media(max-width: 1000px) {

    [data-testid="stHorizontalBlock"] {

        flex-wrap: wrap !important;

    }

    [data-testid="stHorizontalBlock"] > div {

        min-width: 100% !important;

        flex: 1 1 100% !important;

    }

    .nav-center {
        display: none;
    }

    .brand-sub {
        display: none;
    }

    .hero-title {
        font-size: 22px;
    }

    .result-grid,
    .warehouse-grid {
        grid-template-columns: repeat(2, 1fr);
    }

}

@media(max-width: 560px) {

    .stats,
    .result-grid,
    .warehouse-grid {
        grid-template-columns: 1fr !important;
    }

    .hero-title {
        font-size: 19px;
    }

    .telemetry-number {
        font-size: 21px;
    }

    .brand-name {
        font-size: 12px;
    }

}

</style>
""")



# ============================================================
# AUTHENTICATION UI
# ============================================================

st.html("""
<style>
.auth-screen{min-height:62vh;display:flex;align-items:end;justify-content:center;padding:45px 20px 18px;}
.auth-card{width:min(560px,100%);padding:42px 46px 34px;background:radial-gradient(circle at 50% 0%,rgba(5,217,232,.13),transparent 38%),linear-gradient(145deg,rgba(12,15,35,.97),rgba(5,6,18,.98));border:1px solid rgba(5,217,232,.28);box-shadow:0 0 70px rgba(5,217,232,.10);position:relative;overflow:hidden;}
.auth-card:before{content:"";position:absolute;width:170px;height:2px;top:0;left:0;background:linear-gradient(90deg,#05d9e8,transparent);}
.auth-card:after{content:"";position:absolute;width:2px;height:170px;right:0;bottom:0;background:linear-gradient(0deg,#ff2a6d,transparent);}
.auth-brand{text-align:center;color:#05d9e8;font-family:"Orbitron",sans-serif;font-weight:900;font-size:30px;letter-spacing:4px;}
.auth-mark{width:58px;height:58px;margin:0 auto 16px;display:grid;place-items:center;border:1px solid rgba(5,217,232,.5);color:#05d9e8;font-size:25px;box-shadow:0 0 30px rgba(5,217,232,.16);background:rgba(5,217,232,.045);}
.auth-kicker{text-align:center;margin-top:10px;color:#ff4f8b;font:700 11px/1.4 "IBM Plex Mono",monospace;letter-spacing:2px;}
.auth-title{margin:25px 0 7px;text-align:center;color:#f3f7ff;font:800 28px/1.1 "Orbitron",sans-serif;}
.auth-subtitle{text-align:center;color:#8d9bb8;font:500 14px/1.6 "Rajdhani",sans-serif;margin-bottom:25px;}
.auth-security{margin:18px auto 0;max-width:560px;padding:10px 14px;border:1px solid rgba(5,217,232,.12);background:rgba(5,217,232,.035);color:#71819e;text-align:center;font:500 10px/1.6 "IBM Plex Mono",monospace;letter-spacing:.8px;}
</style>
""")


# ============================================================
# LANDING PAGE STYLES
# ============================================================

st.html("""
<style>

.landing-shell {
    min-height: calc(100vh - 20px);
    padding: 18px 2vw 90px 2vw;
    position: relative;
    overflow: hidden;
}

.landing-topbar {
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding: 12px 4px 24px 4px;
    border-bottom:1px solid rgba(255,255,255,.08);
}

.landing-brand { display:flex; align-items:center; gap:12px; }
.landing-brand-mark {
    width:42px; height:42px; display:grid; place-items:center;
    border:1px solid rgba(5,217,232,.55); color:#05d9e8;
    font-family:"Orbitron",sans-serif; font-size:21px;
    box-shadow:0 0 22px rgba(5,217,232,.16), inset 0 0 18px rgba(5,217,232,.08);
}
.landing-brand-name {
    font-family:"Orbitron",sans-serif; font-weight:800; letter-spacing:3px;
    color:#f4f8ff; font-size:16px;
}
.landing-brand-sub {
    margin-left:8px; color:#64718e; font-family:"IBM Plex Mono",monospace;
    font-size:10px; letter-spacing:1px;
}
.landing-status { color:#7d8aa8; font-family:"IBM Plex Mono",monospace; font-size:10px; letter-spacing:1px; }
.landing-status-dot {
    display:inline-block; width:7px; height:7px; border-radius:50%; background:#05d9e8;
    box-shadow:0 0 12px #05d9e8; margin-right:7px;
}

.landing-hero {
    position:relative;
    min-height:690px;
    margin-top:22px;
    display:flex;
    align-items:center;
    overflow:hidden;
    border:1px solid rgba(255,255,255,.09);
    background:
        linear-gradient(90deg, rgba(5,6,18,.99) 0%, rgba(5,6,18,.93) 32%, rgba(5,6,18,.62) 58%, rgba(5,6,18,.22) 100%),
        linear-gradient(180deg, rgba(5,6,18,.05), rgba(5,6,18,.88)),
        url('https://www.softwaredoit.es/images/final-inteligencia-artificial-en-logistica-og.jpg') center/cover no-repeat;
    box-shadow:0 0 70px rgba(5,217,232,.07), inset 0 0 100px rgba(0,0,0,.55);
}

.landing-hero::before {
    content:""; position:absolute; inset:0; pointer-events:none;
    background:
        linear-gradient(115deg, transparent 0%, rgba(5,217,232,.08) 42%, transparent 43%, transparent 67%, rgba(255,42,109,.08) 68%, transparent 69%),
        repeating-linear-gradient(90deg, rgba(255,255,255,.018) 0px, rgba(255,255,255,.018) 1px, transparent 1px, transparent 90px);
}

.landing-hero::after {
    content:""; position:absolute; width:760px; height:760px; right:-330px; bottom:-340px;
    border-radius:50%; border:1px solid rgba(5,217,232,.16);
    box-shadow:0 0 0 55px rgba(5,217,232,.025), 0 0 0 110px rgba(255,42,109,.02);
    pointer-events:none;
}

.landing-copy { position:relative; z-index:4; width:min(780px, 72%); padding:78px 7vw; }
.landing-eyebrow {
    display:inline-flex; align-items:center; gap:8px; padding:7px 11px;
    border:1px solid rgba(5,217,232,.28); background:rgba(5,217,232,.055);
    color:#05d9e8; font-family:"IBM Plex Mono",monospace; font-size:10px;
    letter-spacing:1.8px; text-transform:uppercase; margin-bottom:22px;
}
.landing-eyebrow span { width:6px; height:6px; border-radius:50%; background:#05d9e8; box-shadow:0 0 10px #05d9e8; }
.landing-title {
    margin:0; font-family:"Orbitron",sans-serif; font-weight:900;
    font-size:clamp(44px, 6.3vw, 94px); line-height:.92; letter-spacing:-3px;
    color:#f4f8ff; text-transform:uppercase;
}
.landing-title .cyan { color:#05d9e8; text-shadow:0 0 34px rgba(5,217,232,.25); }
.landing-title .pink { color:#ff2a6d; text-shadow:0 0 34px rgba(255,42,109,.22); }
.landing-tagline {
    margin-top:25px; max-width:650px; color:#aab7d2; font-family:"Rajdhani",sans-serif;
    font-size:20px; line-height:1.45; letter-spacing:.4px;
}
.landing-tagline strong { color:#ffffff; }
.landing-actions { margin-top:32px; display:flex; align-items:center; gap:14px; flex-wrap:wrap; }

/* Signature GRIDPOINT launch control */
.landing-launch-slot { margin:-6px 0 34px 7vw; position:relative; z-index:20; width:min(430px,80%); }
.landing-launch-button { min-height:66px; display:flex; align-items:center; justify-content:center; gap:12px; box-sizing:border-box; width:100%; padding:0 24px; text-decoration:none !important; border-radius:2px; border:1px solid rgba(112,255,225,.72); background:linear-gradient(135deg,#16e0b0 0%,#00a7ff 48%,#7b4dff 100%); color:#04111a !important; font-family:"Orbitron",sans-serif; font-size:15px; font-weight:900; letter-spacing:1.8px; box-shadow:0 0 28px rgba(22,224,176,.22),0 0 60px rgba(0,167,255,.12),inset 0 1px 0 rgba(255,255,255,.38); transition:transform .18s ease,box-shadow .18s ease,filter .18s ease; }
.landing-launch-button span { font-size:21px; }
.landing-launch-button:hover { transform:translateY(-3px) scale(1.015); filter:brightness(1.08); box-shadow:0 0 38px rgba(22,224,176,.36),0 0 90px rgba(0,167,255,.20),inset 0 1px 0 rgba(255,255,255,.45); }
.landing-launch-caption { margin-top:9px; color:#61708c; font-family:"IBM Plex Mono",monospace; font-size:9px; letter-spacing:1.2px; }
.landing-bottom-launch { margin:54px auto 0; max-width:680px; text-align:center; position:relative; z-index:5; }
.landing-bottom-launch .landing-launch-button { min-height:78px; font-size:17px; }
.landing-bottom-launch-note { margin-top:10px; color:#596882; font-family:"IBM Plex Mono",monospace; font-size:9px; letter-spacing:1.2px; }
.landing-action-note { color:#62708d; font-family:"IBM Plex Mono",monospace; font-size:9px; letter-spacing:1px; }
.landing-metrics { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:42px; max-width:690px; }
.landing-metric { padding:16px 18px; border-left:2px solid rgba(5,217,232,.55); background:rgba(7,10,25,.72); backdrop-filter:blur(10px); }
.landing-metric:nth-child(2) { border-left-color:rgba(255,42,109,.65); }
.landing-metric:nth-child(3) { border-left-color:rgba(255,184,0,.65); }
.landing-metric-value { font-family:"Orbitron",sans-serif; font-size:20px; font-weight:800; color:#f4f8ff; }
.landing-metric-label { margin-top:4px; color:#687792; font-family:"IBM Plex Mono",monospace; font-size:8px; letter-spacing:1px; }

/* Logistics network overlay — replaces the unrelated vehicle artwork. */
.landing-network-visual {
    position:absolute; z-index:3; right:3%; top:7%; width:48%; height:86%; pointer-events:none;
}
.landing-network-card {
    position:absolute; inset:7% 2% 7% 8%;
    border:1px solid rgba(5,217,232,.24);
    background:linear-gradient(145deg,rgba(7,12,27,.72),rgba(4,6,18,.34));
    backdrop-filter:blur(3px);
    box-shadow:0 0 55px rgba(5,217,232,.09), inset 0 0 40px rgba(5,217,232,.035);
    overflow:hidden;
}
.landing-network-card::before {
    content:""; position:absolute; inset:0;
    background:
        linear-gradient(30deg, transparent 49.5%, rgba(5,217,232,.13) 49.7%, rgba(5,217,232,.13) 50.2%, transparent 50.4%),
        linear-gradient(150deg, transparent 49.5%, rgba(255,42,109,.12) 49.7%, rgba(255,42,109,.12) 50.2%, transparent 50.4%),
        repeating-linear-gradient(0deg, transparent 0 58px, rgba(255,255,255,.025) 59px),
        repeating-linear-gradient(90deg, transparent 0 76px, rgba(255,255,255,.025) 77px);
    opacity:.8;
}
.landing-network-image {
    position:absolute; inset:0;
    background:
        linear-gradient(90deg,rgba(4,6,18,.84),rgba(4,6,18,.15)),
        url('https://www.atomicloops.com/_next/image?q=75&url=https%3A%2F%2Fd1kmzxl7118mv8.cloudfront.net%2Fimages%2Fai_adoption_logistics_change_mgmt%2Fcase_studies%2Fdhl_case_study.webp&w=3840') center/cover no-repeat;
    opacity:.44;
    filter:saturate(.78) contrast(1.12) brightness(.66) hue-rotate(3deg);
}
.landing-node { position:absolute; width:12px; height:12px; border-radius:50%; background:#05d9e8; box-shadow:0 0 0 5px rgba(5,217,232,.11),0 0 20px #05d9e8; }
.landing-node.pink { background:#ff2a6d; box-shadow:0 0 0 5px rgba(255,42,109,.10),0 0 20px #ff2a6d; }
.landing-node.n1 { left:17%; top:26%; } .landing-node.n2 { left:48%; top:17%; }
.landing-node.n3 { left:72%; top:38%; } .landing-node.n4 { left:38%; top:63%; }
.landing-node.n5 { left:78%; top:76%; } .landing-node.n6 { left:16%; top:78%; }
.landing-route { position:absolute; height:2px; transform-origin:left center; background:linear-gradient(90deg,#05d9e8,#ff2a6d); box-shadow:0 0 10px rgba(5,217,232,.42); opacity:.82; }
.landing-route.r1 { width:38%; left:19%; top:29%; transform:rotate(-15deg); }
.landing-route.r2 { width:33%; left:49%; top:20%; transform:rotate(30deg); }
.landing-route.r3 { width:36%; left:42%; top:65%; transform:rotate(-35deg); }
.landing-route.r4 { width:34%; left:20%; top:80%; transform:rotate(-31deg); }
.landing-route.r5 { width:37%; left:51%; top:66%; transform:rotate(17deg); }
.landing-map-label {
    position:absolute; top:15px; left:17px; color:#05d9e8; font-family:"IBM Plex Mono",monospace;
    font-size:8px; letter-spacing:1.5px; padding:6px 8px; border:1px solid rgba(5,217,232,.25); background:rgba(4,6,18,.68);
}
.landing-map-stats {
    position:absolute; right:16px; bottom:15px; display:grid; gap:6px;
    font-family:"IBM Plex Mono",monospace; font-size:8px; letter-spacing:1px; color:#93a2bd;
}
.landing-map-stat { padding:7px 9px; background:rgba(4,6,18,.78); border-left:2px solid #05d9e8; }
.landing-map-stat:nth-child(2) { border-left-color:#ff2a6d; }
.landing-fleet-tag {
    position:absolute; right:0; top:0; padding:9px 12px; background:rgba(6,6,19,.82);
    border:1px solid rgba(5,217,232,.3); color:#05d9e8; font-family:"IBM Plex Mono",monospace;
    font-size:9px; letter-spacing:1.2px; backdrop-filter:blur(8px);
}
.landing-side-label {
    position:absolute; right:-2px; bottom:6%; transform:rotate(90deg) translateX(50%); transform-origin:right center;
    color:rgba(255,255,255,.28); font-family:"IBM Plex Mono",monospace; font-size:9px; letter-spacing:3px;
}

.landing-feature-section { margin-top:100px; }
.landing-section-kicker { color:#05d9e8; font-family:"IBM Plex Mono",monospace; font-size:10px; letter-spacing:2px; margin-bottom:10px; }
.landing-section-title { font-family:"Orbitron",sans-serif; font-size:clamp(25px,3vw,42px); font-weight:800; color:#f4f8ff; margin-bottom:12px; }
.landing-section-copy { max-width:780px; color:#71809e; font-size:16px; line-height:1.55; }
.landing-feature-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:28px; }
.landing-feature {
    min-height:220px; padding:28px; position:relative; overflow:hidden; border:1px solid rgba(255,255,255,.08);
    background:linear-gradient(145deg,rgba(16,17,38,.92),rgba(8,8,21,.92)); transition:transform .2s ease,border-color .2s ease;
}
.landing-feature:hover { transform:translateY(-5px); border-color:rgba(5,217,232,.28); }
.landing-feature-number { font-family:"IBM Plex Mono",monospace; color:#ff2a6d; font-size:10px; letter-spacing:1px; }
.landing-feature-icon { font-size:31px; margin:24px 0 16px; }
.landing-feature-title { font-family:"Orbitron",sans-serif; color:#f4f8ff; font-size:15px; font-weight:700; letter-spacing:.5px; }
.landing-feature-copy { margin-top:10px; color:#74819d; font-size:14px; line-height:1.5; }

.landing-image-grid {
    margin-top:78px; display:grid; grid-template-columns:1.3fr .85fr .85fr; gap:12px;
}
.landing-image-card {
    min-height:360px; position:relative; overflow:hidden; border:1px solid rgba(255,255,255,.08); background:#080817;
}
.landing-image-card.tall { min-height:430px; }
.landing-image {
    position:absolute; inset:0; background-position:center; background-size:cover; transition:transform .45s ease;
}
.landing-image-card:hover .landing-image { transform:scale(1.035); }
.landing-image-card::after {
    content:""; position:absolute; inset:0; pointer-events:none; z-index:1;
    background: repeating-linear-gradient(0deg, transparent 0 26px, rgba(5,217,232,.035) 27px), linear-gradient(90deg, transparent 0 72%, rgba(5,217,232,.06) 72.2%, transparent 72.5%);
    mix-blend-mode:screen;
}
.landing-image.one {
    background-image:linear-gradient(135deg,rgba(5,217,232,.08),rgba(4,6,18,.05) 42%,rgba(255,42,109,.07) 70%,rgba(4,6,18,.94)),url('https://www.leafio.ai/storage/page/2044/46605efd963c7ea3d45f7a6145e6992207cc93a9.webp');
}
.landing-image.two {
    background-image:linear-gradient(135deg,rgba(5,217,232,.08),rgba(4,6,18,.08) 45%,rgba(123,77,255,.10) 72%,rgba(4,6,18,.92)),url('https://www.eksum.co.in/assets/hero-slide-4-R05mzsBg.jpg');
}
.landing-image.three {
    background-image:linear-gradient(135deg,rgba(255,184,0,.06),rgba(4,6,18,.08) 40%,rgba(5,217,232,.10) 70%,rgba(4,6,18,.92)),url('https://osher.com.au/rails/active_storage/blobs/proxy/eyJfcmFpbHMiOnsiZGF0YSI6NTgsInB1ciI6ImJsb2JfaWQifX0%3D--ab18cac4983e68bc326d9f3a145459f8b61cfc78/ai-in-logistics-smart-logistics.jpg');
}
.landing-image-content { position:absolute; left:24px; right:24px; bottom:22px; z-index:2; }
.landing-image-kicker { color:#05d9e8; font-family:"IBM Plex Mono",monospace; font-size:9px; letter-spacing:1.5px; }
.landing-image-title { margin-top:7px; color:#fff; font-family:"Orbitron",sans-serif; font-size:20px; font-weight:800; }
.landing-image-copy { margin-top:6px; color:#aab7d2; font-size:12px; line-height:1.45; }

.landing-network-strip {
    margin-top:18px; min-height:210px; border:1px solid rgba(5,217,232,.14); background:
        radial-gradient(circle at 20% 30%,rgba(5,217,232,.12),transparent 28%),
        radial-gradient(circle at 78% 70%,rgba(255,42,109,.1),transparent 30%),#080817;
    display:grid; grid-template-columns:1fr 1fr; gap:20px; align-items:center; padding:28px 34px;
}
.landing-network-strip h3 { margin:0; font-family:"Orbitron",sans-serif; color:#f4f8ff; font-size:25px; }
.landing-network-strip p { color:#7887a5; line-height:1.55; font-size:14px; max-width:640px; }
.network-mini { position:relative; height:150px; border:1px solid rgba(255,255,255,.06); overflow:hidden; background-image:url('https://media.licdn.com/dms/image/v2/D4D12AQElPy4HHPNBFg/article-cover_image-shrink_720_1280/B4DZZvJ9LdH4AI-/0/1745621606562?e=2147483647&t=XcDOeplxDY-lg2PsoJiP9T0_TmJxYnRWGEo-MLhEe00&v=beta'); background-size:cover; background-position:center; filter:saturate(.72) brightness(.52); }
.network-mini::after { content:""; position:absolute; inset:0; background:linear-gradient(90deg,rgba(4,6,18,.72),rgba(4,6,18,.3)),repeating-linear-gradient(0deg,transparent 0 28px,rgba(5,217,232,.1) 29px),repeating-linear-gradient(90deg,transparent 0 45px,rgba(5,217,232,.08) 46px); }

.landing-bottom { margin-top:85px; padding:28px 0 15px; display:flex; justify-content:space-between; gap:20px; color:#4e5b77; font-family:"IBM Plex Mono",monospace; font-size:9px; letter-spacing:1px; border-top:1px solid rgba(255,255,255,.07); }
.landing-enter-wrap { margin-top:32px; }

@media(max-width:1050px) {
    .landing-network-visual { opacity:.65; width:53%; right:-2%; }
    .landing-copy { width:74%; }
    .landing-feature-grid { grid-template-columns:repeat(2,1fr); }
    .landing-image-grid { grid-template-columns:1fr 1fr; }
    .landing-image-card:first-child { grid-column:1/-1; }
    .landing-network-strip { grid-template-columns:1fr; }
}
@media(max-width:900px) {
    .landing-copy { width:100%; padding:55px 7vw; }
    .landing-hero { min-height:760px; }
    .landing-network-visual { opacity:.24; width:85%; right:-10%; }
}
@media(max-width:600px) {
    .landing-topbar { align-items:flex-start; }
    .landing-brand-sub,.landing-status { display:none; }
    .landing-title { font-size:42px; letter-spacing:-2px; }
    .landing-tagline { font-size:17px; }
    .landing-metrics { grid-template-columns:1fr; }
    .landing-feature-grid,.landing-image-grid { grid-template-columns:1fr; }
    .landing-image-card:first-child { grid-column:auto; }
    .landing-image-card,.landing-image-card.tall { min-height:300px; }
    .landing-hero { min-height:780px; }
    .landing-network-visual { display:none; }
    .landing-network-strip { padding:24px; }
    .landing-bottom { flex-direction:column; }
}

</style>
""")

# ============================================================
# ANIMATED GAMING BACKGROUND (decorative only — no functional impact)
# ============================================================

st.html("""
<div class="bg-layer">

    <div class="bg-hexgrid"></div>

    <div class="bg-blob bg-blob-magenta"></div>
    <div class="bg-blob bg-blob-cyan"></div>
    <div class="bg-blob bg-blob-purple"></div>

    <div class="bg-sweep"></div>

    <div class="bg-particles">
        <div class="bg-particle" style="left:4%; animation-duration:17s; animation-delay:0s;"></div>
        <div class="bg-particle magenta" style="left:12%; animation-duration:22s; animation-delay:2s;"></div>
        <div class="bg-particle" style="left:20%; animation-duration:15s; animation-delay:5s;"></div>
        <div class="bg-particle magenta" style="left:29%; animation-duration:24s; animation-delay:1s;"></div>
        <div class="bg-particle" style="left:37%; animation-duration:19s; animation-delay:7s;"></div>
        <div class="bg-particle magenta" style="left:45%; animation-duration:27s; animation-delay:3s;"></div>
        <div class="bg-particle" style="left:53%; animation-duration:16s; animation-delay:6s;"></div>
        <div class="bg-particle magenta" style="left:61%; animation-duration:21s; animation-delay:0.5s;"></div>
        <div class="bg-particle" style="left:69%; animation-duration:25s; animation-delay:4s;"></div>
        <div class="bg-particle magenta" style="left:77%; animation-duration:18s; animation-delay:8s;"></div>
        <div class="bg-particle" style="left:85%; animation-duration:23s; animation-delay:2.5s;"></div>
        <div class="bg-particle magenta" style="left:93%; animation-duration:20s; animation-delay:5.5s;"></div>
        <div class="bg-particle" style="left:8%; animation-duration:28s; animation-delay:9s;"></div>
        <div class="bg-particle magenta" style="left:50%; animation-duration:14s; animation-delay:10s;"></div>
        <div class="bg-particle" style="left:80%; animation-duration:26s; animation-delay:11s;"></div>
    </div>

</div>
""")



# ============================================================
# LANDING PAGE
# ============================================================

if "show_dashboard" not in st.session_state:
    st.session_state["show_dashboard"] = False
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "show_auth" not in st.session_state:
    st.session_state["show_auth"] = False

if st.query_params.get("launch") == "1":
    st.session_state["show_auth"] = True
    st.query_params.clear()

if not st.session_state["authenticated"] and not st.session_state["show_auth"]:

    st.html("""
    <div class="landing-shell">

        <div class="landing-topbar">
            <div class="landing-brand">
                <div class="landing-brand-mark">◈</div>
                <div>
                    <span class="landing-brand-name">GRIDPOINT</span>
                    <span class="landing-brand-sub">// LOGISTICS INTELLIGENCE ENGINE</span>
                </div>
            </div>

            <div class="landing-status">
                <span class="landing-status-dot"></span>
                OPTIMIZATION CORE ONLINE
            </div>
        </div>

        <div class="landing-hero">
            <div class="landing-copy">
                <div class="landing-eyebrow"><span></span> DEMAND-DRIVEN LOGISTICS INTELLIGENCE</div>

                <h1 class="landing-title">
                    FIND THE<br>
                    <span class="cyan">RIGHT</span><br>
                    <span class="pink">POINT.</span>
                </h1>

                <div class="landing-tagline">
                    <strong>GRIDPOINT</strong> transforms neighborhood demand into an optimized warehouse network — balancing geography, delivery cost, capacity and service radius in one decision engine.
                </div>

                <div class="landing-enter-wrap">
                    <div class="landing-actions">
                        <div class="landing-action-note">MAP DEMAND → TEST NETWORKS → MAKE THE DECISION</div>
                    </div>
                </div>

                <div class="landing-metrics">
                    <div class="landing-metric">
                        <div class="landing-metric-value">01 → N</div>
                        <div class="landing-metric-label">WAREHOUSE NETWORKS</div>
                    </div>
                    <div class="landing-metric">
                        <div class="landing-metric-value">LIVE</div>
                        <div class="landing-metric-label">DEMAND INPUT</div>
                    </div>
                    <div class="landing-metric">
                        <div class="landing-metric-value">∞</div>
                        <div class="landing-metric-label">SCENARIO POSSIBILITIES</div>
                    </div>
                </div>
            </div>

            <div class="landing-network-visual">
                <div class="landing-network-card">
                    <div class="landing-network-image"></div>
                    <div class="landing-map-label">NETWORK COVERAGE // LIVE MODEL</div>
                    <div class="landing-route r1"></div>
                    <div class="landing-route r2"></div>
                    <div class="landing-route r3"></div>
                    <div class="landing-route r4"></div>
                    <div class="landing-route r5"></div>
                    <div class="landing-node n1"></div>
                    <div class="landing-node n2"></div>
                    <div class="landing-node n3 pink"></div>
                    <div class="landing-node n4 pink"></div>
                    <div class="landing-node n5"></div>
                    <div class="landing-node n6 pink"></div>
                    <div class="landing-map-stats">
                        <div class="landing-map-stat">DEMAND NODES&nbsp;&nbsp; 06</div>
                        <div class="landing-map-stat">WAREHOUSE HUB&nbsp;&nbsp; 02</div>
                    </div>
                </div>
                <div class="landing-fleet-tag">WAREHOUSE × ROUTES × DEMAND</div>
                <div class="landing-side-label">WHERE DEMAND MOVES // WHERE INVENTORY SHOULD SIT</div>
            </div>
        </div>

        <div class="landing-launch-slot">
            <a class="landing-launch-button" href="?launch=1"><span>◈</span> LAUNCH GRIDPOINT</a>
            <div class="landing-launch-caption">PRIMARY ACCESS · OPEN THE OPTIMIZATION CONTROL ROOM</div>
        </div>

        <div class="landing-feature-section">
            <div class="landing-section-kicker">02 / THE DECISION ENGINE</div>
            <div class="landing-section-title">Built for the moment before the warehouse is built.</div>
            <div class="landing-section-copy">
                Stop choosing warehouse locations by intuition alone. GRIDPOINT turns your demand map into a measurable network decision.
            </div>

            <div class="landing-feature-grid">
                <div class="landing-feature">
                    <div class="landing-feature-number">01 · MAP</div>
                    <div class="landing-feature-icon">◉</div>
                    <div class="landing-feature-title">SEE DEMAND</div>
                    <div class="landing-feature-copy">Plot neighborhoods, coordinates and daily order volume on a live network map.</div>
                </div>
                <div class="landing-feature">
                    <div class="landing-feature-number">02 · SOLVE</div>
                    <div class="landing-feature-icon">⌁</div>
                    <div class="landing-feature-title">OPTIMIZE LOCATIONS</div>
                    <div class="landing-feature-copy">Evaluate candidate warehouse combinations against modeled delivery cost and distance.</div>
                </div>
                <div class="landing-feature">
                    <div class="landing-feature-number">03 · CONSTRAIN</div>
                    <div class="landing-feature-icon">▣</div>
                    <div class="landing-feature-title">CONTROL REALITY</div>
                    <div class="landing-feature-copy">Apply warehouse capacity and maximum delivery-radius constraints to the network.</div>
                </div>
                <div class="landing-feature">
                    <div class="landing-feature-number">04 · DECIDE</div>
                    <div class="landing-feature-icon">↗</div>
                    <div class="landing-feature-title">MEASURE IMPACT</div>
                    <div class="landing-feature-copy">Compare the baseline and optimized network through cost, distance and estimated travel time.</div>
                </div>
            </div>
        </div>

        <div class="landing-image-grid">
            <div class="landing-image-card tall">
                <div class="landing-image one"></div>
                <div class="landing-image-content">
                    <div class="landing-image-kicker">01 / LAST-MILE REALITY</div>
                    <div class="landing-image-title">From warehouse dock to delivery network.</div>
                    <div class="landing-image-copy">Every order starts somewhere. GRIDPOINT helps determine where that starting point should be.</div>
                </div>
            </div>
            <div class="landing-image-card">
                <div class="landing-image two"></div>
                <div class="landing-image-content">
                    <div class="landing-image-kicker">02 / FLEET MOVEMENT</div>
                    <div class="landing-image-title">Vehicles follow the network.</div>
                    <div class="landing-image-copy">Location decisions shape the distances your delivery fleet has to cover.</div>
                </div>
            </div>
            <div class="landing-image-card">
                <div class="landing-image three"></div>
                <div class="landing-image-content">
                    <div class="landing-image-kicker">03 / NETWORK SCALE</div>
                    <div class="landing-image-title">See the system from above.</div>
                    <div class="landing-image-copy">Demand, facilities and routes become one connected planning problem.</div>
                </div>
            </div>
        </div>

        <div class="landing-network-strip">
            <div>
                <div class="landing-section-kicker">04 / WHY LOCATION MATTERS</div>
                <h3>Every kilometer has a price.</h3>
                <p>
                    A warehouse network is more than dots on a map. It determines how far vehicles travel, how quickly demand is served and how efficiently every order moves through the system.
                </p>
                <p><strong style="color:#05d9e8;">GRIDPOINT makes that trade-off visible.</strong></p>
            </div>
            <div class="network-mini"></div>
        </div>

        <div class="landing-bottom">
            <div>GRIDPOINT // DEMAND · GEOGRAPHY · COST · CAPACITY</div>
            <div>PLANNING INTELLIGENCE / v1.0</div>
        </div>

    </div>
    """)

    st.html("""
    <div style="height:8px;"></div>
    """)

    st.html("""
    <div style="height:18px;"></div>
    <div class="landing-bottom-launch">
        <div class="landing-bottom-launch-note">READY WHEN YOU ARE · DEMAND → NETWORK → DECISION</div>
        <a class="landing-launch-button" href="?launch=1"><span>◈</span> ENTER GRIDPOINT CONTROL ROOM</a>
        <div class="landing-bottom-launch-note">OPTIMIZATION CORE ONLINE · OPEN THE LIVE PLANNING WORKSPACE</div>
    </div>
    """)

    st.stop()


# ============================================================
# AUTHENTICATION SCREEN
# ============================================================

if not st.session_state["authenticated"]:
    st.html("""
    <div class="auth-screen">
        <div class="auth-card">
            <div class="auth-mark">◈</div>
            <div class="auth-brand">GRIDPOINT</div>
            <div class="auth-kicker">CONTROL ROOM ACCESS // AUTHENTICATION REQUIRED</div>
            <div class="auth-title">WELCOME BACK, OPERATOR.</div>
            <div class="auth-subtitle">Authenticate to enter the GRIDPOINT logistics intelligence control room.</div>
        </div>
    </div>
    """)

    with st.form("gridpoint_login", clear_on_submit=False):
        email = st.text_input("EMAIL", placeholder="operator@company.com", key="login_email")
        password = st.text_input("PASSWORD", type="password", placeholder="Enter your access password", key="login_password")
        submitted = st.form_submit_button("◈  ACCESS CONTROL ROOM", use_container_width=True)

    if submitted:
        if verify_credentials(email, password):
            st.session_state["authenticated"] = True
            st.session_state["show_dashboard"] = True
            st.session_state["show_auth"] = False
            st.session_state.pop("login_password", None)
            st.rerun()
        else:
            st.error("Access denied. Check your email and password.")

    st.html("""
    <div class="auth-security">SECURE SESSION · GRIDPOINT CONTROL ROOM · AUTHORIZED ACCESS ONLY</div>
    """)
    st.stop()


# ============================================================
# TOP NAV
# ============================================================

st.html("""
<div class="nav">

    <div class="brand">

        <div class="brand-mark">
            ◈
        </div>

        <div>

            <span class="brand-name">
                GRIDPOINT
            </span>

            <span class="brand-sub">
                // LOGISTICS INTELLIGENCE ENGINE
            </span>

        </div>

    </div>


    <div class="nav-center">
        DEMAND // GEOGRAPHY // COST // CAPACITY
    </div>


    <div class="live">
        <span class="live-dot"></span>
        SYSTEM ONLINE
    </div>

</div>
""")

logout_spacer, logout_col = st.columns([12, 1])
with logout_col:
    if st.button("LOG OUT", key="gridpoint_logout"):
        st.session_state["authenticated"] = False
        st.session_state["show_dashboard"] = False
        st.session_state["show_auth"] = False
        st.rerun()


# ============================================================
# MAIN DASHBOARD
# ============================================================

left_col, center_col, right_col = st.columns(
    [3.0, 9.4, 3.6],
    gap="small"
)


# ============================================================
# LEFT PANEL
# ============================================================

with left_col:

    st.html("""
    <div class="panel">

        <div class="panel-header">

            <div class="panel-title">
                ◉ NETWORK INPUT
            </div>

            <div class="panel-tag">
                DATA
            </div>

        </div>

        <div class="line"></div>

    </div>
    """)


    input_method = st.radio(
        "Input method",
        [
            "📂 CSV",
            "✍️ MANUAL",
        ],
        horizontal=True,
        label_visibility="collapsed",
    )


    if input_method == "📂 CSV":

        uploaded_file = st.file_uploader(
            "Upload CSV",
            type=["csv"],
            label_visibility="collapsed",
            key="network_csv_uploader",
        )


        # The uploaded CSV is ALWAYS the active dataset while a file
        # is selected. This deliberately does not depend on a previous
        # session-state signature, so old demo data cannot remain active.
        if uploaded_file is not None:

            try:

                uploaded_bytes = uploaded_file.getvalue()
                signature = hashlib.md5(uploaded_bytes).hexdigest()

                uploaded_data = pd.read_csv(
                    io.BytesIO(uploaded_bytes)
                )

                # Always refresh the active dataset from the actual
                # uploaded bytes. This prevents stale sample_data.csv
                # results from surviving a new upload.
                if (
                    signature != st.session_state.get("loaded_file_signature")
                    or "data" not in st.session_state
                ):
                    load_data(uploaded_data)
                    st.session_state["loaded_file_signature"] = signature
                else:
                    # Even when the file signature is unchanged, make
                    # sure the active data is the uploaded CSV, not demo
                    # data left in session state.
                    st.session_state["data"] = uploaded_data.copy()

            except Exception as error:

                st.error(
                    f"CSV error: {error}"
                )


        demo_button = st.button(
            "▣  LOAD DEMO DATA",
            use_container_width=True,
            disabled=uploaded_file is not None,
        )


        if demo_button:

            try:

                load_data(
                    pd.read_csv(
                        "sample_data.csv"
                    )
                )

                # Mark the demo as a different active dataset.
                st.session_state["loaded_file_signature"] = None

                st.success(
                    "Demo loaded."
                )

            except FileNotFoundError:

                st.error(
                    "sample_data.csv not found."
                )


    else:

        manual_data = st.data_editor(

            pd.DataFrame(
                {
                    "Neighborhood": [
                        "Area 1",
                        "Area 2",
                        "Area 3",
                    ],
                    "Latitude": [
                        12.9352,
                        12.9784,
                        12.9250,
                    ],
                    "Longitude": [
                        77.6245,
                        77.6408,
                        77.5938,
                    ],
                    "Orders": [
                        500,
                        300,
                        250,
                    ],
                }
            ),

            num_rows="dynamic",

            use_container_width=True,

            hide_index=True,

        )


        if st.button(
            "✓  USE NETWORK",
            use_container_width=True,
        ):

            load_data(
                manual_data
            )

            st.success(
                "Network loaded."
            )


    # ========================================================
    # CONTROLS IF DATA EXISTS
    # ========================================================

    if "data" in st.session_state:

        data = (
            st.session_state[
                "data"
            ].copy()
        )


        required = [
            "Neighborhood",
            "Latitude",
            "Longitude",
            "Orders",
        ]


        missing = [
            x
            for x in required
            if x not in data.columns
        ]


        if missing:

            st.error(
                "Missing columns: "
                + ", ".join(missing)
            )

            st.stop()


        data["Latitude"] = pd.to_numeric(
            data["Latitude"],
            errors="coerce"
        )

        data["Longitude"] = pd.to_numeric(
            data["Longitude"],
            errors="coerce"
        )

        data["Orders"] = pd.to_numeric(
            data["Orders"],
            errors="coerce"
        )


        if (
            data.empty
            or
            data["Latitude"].isna().any()
            or
            data["Longitude"].isna().any()
            or
            data["Orders"].isna().any()
            or
            (data["Orders"] < 0).any()
        ):

            st.error(
                "Please check your input data."
            )

            st.stop()


        st.session_state[
            "data"
        ] = data


        total_orders = data[
            "Orders"
        ].sum()

        location_count = len(
            data
        )


        # ----------------------------------------------------
        # NETWORK STATS
        # ----------------------------------------------------

        st.html(
            f"""
<div class="stats">

    <div class="stat">

        <div class="stat-label">
            LOCATIONS
        </div>

        <div class="stat-value blue">
            {location_count}
        </div>

    </div>


    <div class="stat">

        <div class="stat-label">
            DAILY ORDERS
        </div>

        <div class="stat-value green">
            {int(total_orders):,}
        </div>

    </div>


    <div class="stat">

        <div class="stat-label">
            AVG / AREA
        </div>

        <div class="stat-value orange">
            {int(total_orders / location_count):,}
        </div>

    </div>

</div>
"""
        )


        # ----------------------------------------------------
        # CONFIG
        # ----------------------------------------------------

        st.html("""
        <div class="control-box">

            <div class="control-label">
                NETWORK CONFIGURATION
            </div>

        </div>
        """)


        number_of_warehouses = st.number_input(
            "🏭 WAREHOUSES",
            min_value=1,
            max_value=min(
                5,
                len(data)
            ),
            value=1,
            step=1,
        )


        cost_per_km = st.number_input(
            "₹ COST / KM",
            min_value=1.0,
            value=20.0,
            step=1.0,
        )


        average_speed = st.number_input(
            "🚚 VEHICLE SPEED",
            min_value=1.0,
            max_value=150.0,
            value=30.0,
            step=1.0,
        )


        st.html("""
        <div class="control-box">

            <div class="control-label">
                OPTIONAL CONSTRAINTS
            </div>

        </div>
        """)


        use_radius = st.checkbox(
            "📏 MAXIMUM SERVICE RADIUS"
        )


        if use_radius:

            max_radius = st.number_input(
                "Radius (km)",
                min_value=0.1,
                value=10.0,
                step=0.5,
            )

        else:

            max_radius = None


        use_capacity = st.checkbox(
            "📦 WAREHOUSE CAPACITY"
        )


        if use_capacity:

            warehouse_capacity = st.number_input(
                "Orders / warehouse / day",
                min_value=1,
                value=1500,
                step=100,
            )

        else:

            warehouse_capacity = None


        st.html(
            "<div style='height:5px'></div>"
        )


        optimize_button = st.button(
            "⚡  OPTIMIZE NETWORK",
            type="primary",
            use_container_width=True,
        )


        reset_button = st.button(
            "↺  RESET ANALYSIS",
            use_container_width=True,
        )


        if reset_button:
            clear_results()


        with st.expander(
            "▣ VIEW RAW DATA"
        ):

            st.dataframe(
                data,
                use_container_width=True,
                hide_index=True,
            )


# ============================================================
# RUN OPTIMIZATION
# ============================================================

if (
    "data" in st.session_state
    and
    optimize_button
):

    with st.spinner(
        "GRIDPOINT is calculating the optimal network..."
    ):

        result = find_best_warehouses(

            data,

            int(
                number_of_warehouses
            ),

            cost_per_km,

            max_radius,

            warehouse_capacity,

        )


    clear_results()


    if result is None:

        st.session_state[
            "optimization_failed"
        ] = True

    else:

        (
            warehouses,
            total_distance,
            weighted_distance,
            total_cost,
            assignments,
        ) = result


        (
            baseline_lat,
            baseline_lon,
            baseline_distance,
            baseline_weighted_distance,
            baseline_cost,
        ) = calculate_baseline(
            data,
            cost_per_km
        )


        average_time = (
            calculate_average_travel_time(
                weighted_distance,
                total_orders,
                average_speed
            )
        )


        baseline_time = (
            calculate_average_travel_time(
                baseline_weighted_distance,
                total_orders,
                average_speed
            )
        )


        st.session_state.update(
            {
                "warehouses":
                    warehouses,

                "assignments":
                    assignments,

                "total_cost":
                    total_cost,

                "total_distance":
                    total_distance,

                "weighted_distance":
                    weighted_distance,

                "baseline_cost":
                    baseline_cost,

                "baseline_lat":
                    baseline_lat,

                "baseline_lon":
                    baseline_lon,

                "baseline_distance":
                    baseline_distance,

                "average_time":
                    average_time,

                "baseline_time":
                    baseline_time,

                "optimization_failed":
                    False,
            }
        )


# ============================================================
# CENTER MAP
# ============================================================

if "data" in st.session_state:

    data = (
        st.session_state[
            "data"
        ].copy()
    )


    with center_col:

        st.html("""
        <div class="hero">

            <div class="hero-kicker">
                DEMAND × GEOGRAPHY × OPTIMIZATION
            </div>

            <div class="hero-title">
                Find the
                <span>right place</span>
                for your warehouse.
            </div>

            <div class="hero-copy">
                Demand-driven warehouse placement using
                geographic distance, order volume, operating
                cost and optional network constraints.
            </div>

        </div>
        """)


        # ----------------------------------------------------
        # MODEL DELTA
        # ----------------------------------------------------

        if "total_cost" in st.session_state:

            baseline_cost = (
                st.session_state[
                    "baseline_cost"
                ]
            )

            optimized_cost = (
                st.session_state[
                    "total_cost"
                ]
            )

            saving = (
                baseline_cost
                -
                optimized_cost
            )

            saving_pct = (

                saving
                /
                baseline_cost
                *
                100

                if baseline_cost > 0

                else 0
            )


            st.html(
                f"""
<div class="telemetry">

    <div class="telemetry-label">
        MODEL DELTA
    </div>

    <div
        style="
        color:#8b98b8;
        font-family:'IBM Plex Mono';
        font-size:8px;
        margin-top:5px;
        "
    >
        BASELINE COST
        <span style="color:#d7deee">
            ₹{baseline_cost:,.0f}
        </span>

        &nbsp; →

        OPTIMIZED
        <span class="green">
            ₹{optimized_cost:,.0f}
        </span>

        &nbsp;

        <span class="green">
            ({saving_pct:+.1f}%)
        </span>

    </div>

</div>
"""
            )


        # ----------------------------------------------------
        # MAP
        # ----------------------------------------------------

        # Use OpenStreetMap as the base layer instead of CARTO Dark Matter.
        # CARTO now requires an API key for its public basemaps, which is why
        # the old map displayed the distracting "API key required" watermark.
        # The map data, markers, warehouse locations and delivery connections
        # remain exactly the same; only the basemap source/styling is changed.
        network_map = folium.Map(

            location=[
                data["Latitude"].mean(),
                data["Longitude"].mean(),
            ],

            zoom_start=12,

            tiles="OpenStreetMap",

            attr="© OpenStreetMap contributors",

            control_scale=True,

            prefer_canvas=True,

        )

        # Darken the OpenStreetMap tiles so they visually match the GRIDPOINT
        # gaming-HUD interface without changing the actual map information.
        network_map.get_root().html.add_child(
            folium.Element(
                """
                <style>
                    .leaflet-tile-pane img {
                        filter: brightness(0.42) saturate(0.72) contrast(1.18);
                    }

                    .leaflet-control-attribution {
                        background: rgba(6, 6, 19, 0.82) !important;
                        color: #8b98b8 !important;
                        border: 1px solid rgba(5, 217, 232, 0.16);
                        border-radius: 0 !important;
                        font-family: Arial, sans-serif;
                        font-size: 10px;
                        padding: 2px 5px !important;
                    }

                    .leaflet-control-attribution a {
                        color: #05d9e8 !important;
                    }

                    .leaflet-control-zoom a {
                        background: rgba(8, 8, 20, 0.92) !important;
                        color: #05d9e8 !important;
                        border-color: rgba(5, 217, 232, 0.22) !important;
                    }

                    .leaflet-control-zoom a:hover {
                        background: rgba(255, 42, 109, 0.18) !important;
                        color: #ffffff !important;
                    }
                </style>
                """
            )
        )

        # A subtle HUD-style frame around the map itself.
        network_map.get_root().html.add_child(
            folium.Element(
                """
                <style>
                    .leaflet-container {
                        background: #060613 !important;
                    }
                </style>
                """
            )
        )


        # DEMAND

        for _, row in data.iterrows():

            folium.CircleMarker(

                location=[
                    row["Latitude"],
                    row["Longitude"],
                ],

                radius=max(5, min(11, 4 + (float(row["Orders"]) ** 0.5) / 4)),

                popup=(
                    f"<b>{row['Neighborhood']}</b><br>"
                    f"Daily Orders: "
                    f"{int(row['Orders']):,}"
                ),

                tooltip=(
                    f"{row['Neighborhood']} · "
                    f"{int(row['Orders']):,} orders"
                ),

                color="#22d3ee",

                fill=True,

                fill_color="#ff9f1c",

                fill_opacity=.95,

                weight=2,

            ).add_to(
                network_map
            )


        # BASELINE

        if "baseline_lat" in st.session_state:

            folium.Marker(

                location=[
                    st.session_state[
                        "baseline_lat"
                    ],

                    st.session_state[
                        "baseline_lon"
                    ],
                ],

                popup="Demand-weighted baseline",

                tooltip="Demand-weighted baseline",

                icon=folium.DivIcon(
                    html="""
                    <div style="width:30px;height:30px;border-radius:50%;background:rgba(5,217,232,.18);border:2px solid #05d9e8;box-shadow:0 0 18px rgba(5,217,232,.75);display:flex;align-items:center;justify-content:center;color:#fff;font-family:Arial,sans-serif;font-size:15px;font-weight:bold;">i</div>
                    """
                ),

            ).add_to(
                network_map
            )


        # WAREHOUSES + LINES

        if "warehouses" in st.session_state:

            for warehouse in (
                st.session_state[
                    "warehouses"
                ]
            ):

                folium.Marker(

                    location=[
                        warehouse["Latitude"],
                        warehouse["Longitude"],
                    ],

                    popup=(
                        "<b>OPTIMIZED WAREHOUSE</b><br>"
                        f"{warehouse['Neighborhood']}"
                    ),

                    tooltip=(
                        f"🏭 {warehouse['Neighborhood']}"
                    ),

                    icon=folium.DivIcon(
                        html="""
                        <div style="width:38px;height:38px;border-radius:50%;background:rgba(255,42,109,.20);border:2px solid #ff2a6d;box-shadow:0 0 10px rgba(255,42,109,.65),0 0 28px rgba(5,217,232,.35);display:flex;align-items:center;justify-content:center;color:#fff;font-size:18px;text-shadow:0 0 8px #fff;">⌂</div>
                        """
                    ),

                ).add_to(
                    network_map
                )


            # Collect route coordinates for animated direction markers.
            animated_routes = []
            route_palette = [
                "#05d9e8",
                "#a970ff",
                "#ffb800",
                "#ff4f8b",
                "#66f7b2",
                "#7aa7ff",
            ]

            for assignment_index, assignment in enumerate(
                st.session_state[
                    "assignments"
                ]
            ):

                nrows = data[
                    data[
                        "Neighborhood"
                    ].astype(str)
                    ==
                    str(
                        assignment[
                            "Neighborhood"
                        ]
                    )
                ]


                wrows = data[
                    data[
                        "Neighborhood"
                    ].astype(str)
                    ==
                    str(
                        assignment[
                            "Warehouse"
                        ]
                    )
                ]


                if (
                    nrows.empty
                    or
                    wrows.empty
                ):

                    continue


                n = nrows.iloc[0]
                w = wrows.iloc[0]

                # Route the visual connection along the actual road network.
                # The optimization mathematics remains unchanged.
                straight_locations = [
                    [n["Latitude"], n["Longitude"]],
                    [w["Latitude"], w["Longitude"]],
                ]

                road_locations = get_road_route(
                    n["Latitude"],
                    n["Longitude"],
                    w["Latitude"],
                    w["Longitude"],
                )

                connection_locations = (
                    road_locations
                    if road_locations
                    else straight_locations
                )

                route_color = route_palette[
                    assignment_index % len(route_palette)
                ]

                # Keep the glow subtle so overlapping road segments remain readable.
                folium.PolyLine(
                    locations=connection_locations,
                    color=route_color,
                    weight=7,
                    opacity=.08,
                ).add_to(network_map)

                # Thin, color-coded road-following route. Different routes get
                # different colors so shared road segments are easier to distinguish.
                folium.PolyLine(
                    locations=connection_locations,
                    color=route_color,
                    weight=2.2,
                    opacity=.78,
                    dash_array="10 7",
                    tooltip=(
                        f"{assignment['Neighborhood']} → "
                        f"{assignment['Warehouse']} · "
                        f"{assignment['Distance_km']:.2f} km"
                    ),
                ).add_to(network_map)

                if road_locations and len(road_locations) >= 2:
                    animated_routes.append({
                        "route": connection_locations,
                        "color": route_color,
                    })


            # Animated direction dots: each dot travels from neighborhood to
            # warehouse and back again. This is visual guidance only; it does
            # not alter the optimizer or route calculations.
            if animated_routes:
                map_name = network_map.get_name()
                routes_json = json.dumps(animated_routes)
                network_map.get_root().html.add_child(
                    folium.Element(
                        f"""
                        <style>
                            .gridpoint-route-ball {{
                                filter: drop-shadow(0 0 5px rgba(255,255,255,.95)) drop-shadow(0 0 10px rgba(5,217,232,.65));
                            }}
                            .gridpoint-route-halo {{
                                filter: drop-shadow(0 0 12px rgba(5,217,232,.45));
                            }}
                        </style>
                        <script>
                        (function() {{
                            const map = {map_name};
                            const routes = {routes_json};
                            const movers = [];

                            function lerp(a, b, t) {{
                                return a + (b - a) * t;
                            }}

                            function pointOnRoute(route, t) {{
                                if (!route || route.length < 2) return route[0];
                                const scaled = t * (route.length - 1);
                                const i = Math.min(Math.floor(scaled), route.length - 2);
                                const localT = scaled - i;
                                const a = route[i];
                                const b = route[i + 1];
                                return [
                                    lerp(a[0], b[0], localT),
                                    lerp(a[1], b[1], localT)
                                ];
                            }}

                            routes.forEach(function(item, index) {{
                                const point = pointOnRoute(item.route, 0);
                                // Bright moving route ball: a white-hot core with a colored
                                // outer ring and a larger glow. It travels along the actual
                                // road geometry and reverses direction at the destination.
                                const marker = L.circleMarker(point, {{
                                    radius: 5.5,
                                    color: '#ffffff',
                                    weight: 2,
                                    opacity: 1,
                                    fillColor: item.color,
                                    fillOpacity: 1,
                                    interactive: false,
                                    className: 'gridpoint-route-ball'
                                }}).addTo(map);

                                // Large soft halo behind the moving ball.
                                const halo = L.circleMarker(point, {{
                                    radius: 13,
                                    color: item.color,
                                    weight: 2,
                                    opacity: 0.28,
                                    fillColor: item.color,
                                    fillOpacity: 0.12,
                                    interactive: false,
                                    className: 'gridpoint-route-halo'
                                }}).addTo(map);

                                movers.push({{
                                    marker: marker,
                                    halo: halo,
                                    route: item.route,
                                    offset: (index * 0.19) % 1,
                                    speed: 0.000075 + ((index % 3) * 0.000018)
                                }});
                            }});

                            let last = performance.now();
                            function animate(now) {{
                                const dt = now - last;
                                last = now;

                                movers.forEach(function(m) {{
                                    m.offset += m.speed * dt;
                                    if (m.offset > 1) m.offset -= 1;

                                    // Ping-pong motion: outbound, then return.
                                    const phase = m.offset < 0.5
                                        ? m.offset * 2
                                        : 2 - (m.offset * 2);
                                    const point = pointOnRoute(m.route, phase);
                                    m.marker.setLatLng(point);
                                    m.halo.setLatLng(point);
                                }});

                                requestAnimationFrame(animate);
                            }}

                            requestAnimationFrame(animate);
                        }})();
                        </script>
                        """
                    )
                )


        network_map.get_root().html.add_child(
            folium.Element(
                """
                <div style="position:fixed;top:12px;right:12px;z-index:9999;background:rgba(6,6,19,.88);border:1px solid rgba(5,217,232,.28);box-shadow:0 0 20px rgba(5,217,232,.12);padding:9px 11px;color:#dce8ff;font-family:Arial,sans-serif;font-size:11px;line-height:1.8;backdrop-filter:blur(8px);">
                    <div style="color:#05d9e8;font-weight:bold;letter-spacing:1px;margin-bottom:3px;">NETWORK MAP</div>
                    <div><span style="color:#ffb800;font-size:16px;">●</span> Demand</div>
                    <div><span style="color:#ff2a6d;font-size:16px;">⌂</span> Warehouse</div>
                    <div><span style="color:#05d9e8;font-size:16px;">i</span> Baseline</div>
                    <div><span style="color:#7aa7ff;font-size:16px;">━</span> Road delivery route</div>
                    <div><span style="color:#ffffff;font-size:15px;text-shadow:0 0 7px #fff;">●</span> Moving route ball</div>
                </div>
                """
            )
        )

        st.html(
            '<div class="map-box">'
        )


        st_folium(
            network_map,
            width=None,
            height=720,
            returned_objects=[],
        )


        st.html(
            '</div>'
        )


# ============================================================
# RIGHT TELEMETRY
# ============================================================

if "data" in st.session_state:

    with right_col:

        st.html("""
        <div class="panel-header">

            <div class="panel-title">
                ◈ OPTIMIZATION TELEMETRY
            </div>

            <div class="panel-tag">
                LIVE
            </div>

        </div>

        <div class="line"></div>
        """)


        if "total_cost" in st.session_state:

            baseline_cost = (
                st.session_state[
                    "baseline_cost"
                ]
            )

            optimized_cost = (
                st.session_state[
                    "total_cost"
                ]
            )

            saving = (
                baseline_cost
                -
                optimized_cost
            )

            saving_pct = (

                saving
                /
                baseline_cost
                *
                100

                if baseline_cost > 0

                else 0
            )

            total_distance = (
                st.session_state[
                    "total_distance"
                ]
            )

            baseline_distance = (
                st.session_state[
                    "baseline_distance"
                ]
            )

            average_time = (
                st.session_state[
                    "average_time"
                ]
            )

            baseline_time = (
                st.session_state[
                    "baseline_time"
                ]
            )

            time_saved = (
                baseline_time
                -
                average_time
            )


            # SAVINGS

            st.html(
                f"""
<div class="telemetry">

    <div class="telemetry-label">
        ESTIMATED SAVINGS
    </div>

    <div class="telemetry-number green">
        ₹{saving:,.0f}
    </div>

    <div class="telemetry-note">
        {saving_pct:+.1f}% vs demand-weighted baseline
    </div>

</div>
"""
            )


            # DISTANCE

            st.html(
                f"""
<div class="telemetry">

    <div class="telemetry-label">
        TOTAL DELIVERY DISTANCE
    </div>

    <div class="compare">

        <div class="compare-cell">

            <div class="compare-label">
                BASELINE
            </div>

            <div class="compare-value">
                {baseline_distance:.1f} km
            </div>

        </div>


        <div class="compare-cell">

            <div class="compare-label">
                OPTIMIZED
            </div>

            <div class="compare-value cyan">
                {total_distance:.1f} km
            </div>

        </div>

    </div>

</div>
"""
            )


            # COST

            st.html(
                f"""
<div class="telemetry">

    <div class="telemetry-label">
        WEIGHTED DELIVERY COST
    </div>

    <div class="compare">

        <div class="compare-cell">

            <div class="compare-label">
                BASELINE
            </div>

            <div class="compare-value">
                ₹{baseline_cost:,.0f}
            </div>

        </div>


        <div class="compare-cell">

            <div class="compare-label">
                OPTIMIZED
            </div>

            <div class="compare-value green">
                ₹{optimized_cost:,.0f}
            </div>

        </div>

    </div>

</div>
"""
            )


            # TIME

            st.html(
                f"""
<div class="stats">

    <div class="stat">

        <div class="stat-label">
            AVG TRAVEL
        </div>

        <div class="stat-value orange">
            {average_time:.1f}m
        </div>

    </div>


    <div class="stat">

        <div class="stat-label">
            TIME SAVED
        </div>

        <div class="stat-value green">
            {time_saved:.1f}m
        </div>

    </div>

</div>
"""
            )


            # ASSIGNMENTS

            st.html("""
            <div class="control-box">

                <div class="control-label">
                    WAREHOUSE ASSIGNMENTS
                </div>

            </div>
            """)


            assignments = (
                st.session_state[
                    "assignments"
                ]
            )


            warehouse_orders = {}


            for assignment in assignments:

                name = (
                    assignment[
                        "Warehouse"
                    ]
                )

                warehouse_orders[
                    name
                ] = (

                    warehouse_orders.get(
                        name,
                        0
                    )

                    +

                    assignment[
                        "Orders"
                    ]

                )


            for name, orders in (
                warehouse_orders.items()
            ):

                if warehouse_capacity:

                    percentage = (
                        orders
                        /
                        warehouse_capacity
                        *
                        100
                    )

                else:

                    percentage = 0


                display_percentage = min(
                    100,
                    max(
                        0,
                        percentage
                    )
                )


                st.html(
                    f"""
<div class="assignment">

    <div class="assignment-top">

        <div class="assignment-name">
            ■ {name}
        </div>

        <div class="assignment-value">
            {int(orders):,}
        </div>

    </div>


    <div
        style="
        color:#6b7a99;
        font-family:'IBM Plex Mono';
        font-size:7px;
        margin-top:3px;
        "
    >
        DAILY ORDERS

    </div>


    <div class="progress">

        <div
            class="progress-fill"
            style="
            width:{display_percentage}%;
            "
        ></div>

    </div>


    <div
        style="
        color:#6b7a99;
        font-family:'IBM Plex Mono';
        font-size:6px;
        margin-top:4px;
        "
    >
        {
            f"{percentage:.0f}% CAPACITY"
            if warehouse_capacity
            else "CAPACITY UNLIMITED"
        }

    </div>

</div>
"""
                )


        else:

            st.html("""
<div class="telemetry">

    <div class="telemetry-label">
        SYSTEM STATE
    </div>

    <div
        class="telemetry-number cyan"
        style="font-size:18px"
    >
        READY
    </div>

    <div class="telemetry-note">
        Configure the network and run optimization.
    </div>

</div>
""")


# ============================================================
# HOW GRIDPOINT WORKS
# ============================================================

st.html("""
<div class="workflow-section">

    <div class="section-kicker">
        01 / DECISION WORKFLOW
    </div>

    <div class="section-heading">
        How GRIDPOINT turns demand into a warehouse plan
    </div>

    <div class="section-rule"></div>

    <div class="workflow-grid">

        <div class="workflow-card">
            <div class="workflow-number">01 · INPUT</div>
            <div class="workflow-title">Load demand</div>
            <div class="workflow-copy">
                Upload a CSV or enter neighborhoods manually with latitude, longitude and daily orders.
            </div>
        </div>

        <div class="workflow-card">
            <div class="workflow-number">02 · CONFIG</div>
            <div class="workflow-title">Set the network</div>
            <div class="workflow-copy">
                Choose warehouse count, delivery cost and assumed vehicle speed. Add radius or capacity limits when needed.
            </div>
        </div>

        <div class="workflow-card">
            <div class="workflow-number">03 · SOLVE</div>
            <div class="workflow-title">Optimize locations</div>
            <div class="workflow-copy">
                GRIDPOINT evaluates feasible warehouse combinations and selects the network with the lowest modeled delivery cost.
            </div>
        </div>

        <div class="workflow-card">
            <div class="workflow-number">04 · ASSIGN</div>
            <div class="workflow-title">Connect demand</div>
            <div class="workflow-copy">
                Each neighborhood is assigned to a selected warehouse while respecting the active service constraints.
            </div>
        </div>

        <div class="workflow-card">
            <div class="workflow-number">05 · DECIDE</div>
            <div class="workflow-title">Compare impact</div>
            <div class="workflow-copy">
                Review cost, distance, estimated travel time, warehouse load and the before-versus-optimized network.
            </div>
        </div>

    </div>

    <div class="demo-note">
        <strong style="color:#05d9e8;">DEMO TIP ·</strong> Start with the sample network, run the optimization, then upload a different city CSV to demonstrate that GRIDPOINT recalculates the network from the new demand data.
    </div>

</div>
""")


# ============================================================
# FAILURE
# ============================================================

if st.session_state.get(
    "optimization_failed",
    False
):

    st.error(
        "No feasible warehouse configuration was found for the current constraints."
    )

    st.html("""
    <div class="error-guide">
        <strong>TRY THIS:</strong> increase the number of warehouses, increase warehouse capacity, or increase the maximum service radius. If both radius and capacity are enabled, make sure the constraints can cover every neighborhood in the dataset.
    </div>
    """)


# ============================================================
# RESULTS
# ============================================================

if "warehouses" in st.session_state:

    st.html("""
    <div class="section-kicker">
        02 / OPTIMIZATION OUTPUT
    </div>

    <div class="section-heading">
        Network recommendation
    </div>

    <div class="section-rule"></div>
    """)


    total_distance = (
        st.session_state[
            "total_distance"
        ]
    )

    weighted_distance = (
        st.session_state[
            "weighted_distance"
        ]
    )

    total_cost = (
        st.session_state[
            "total_cost"
        ]
    )

    baseline_cost = (
        st.session_state[
            "baseline_cost"
        ]
    )

    average_time = (
        st.session_state[
            "average_time"
        ]
    )


    saving = (
        baseline_cost
        -
        total_cost
    )

    saving_pct = (
        saving
        /
        baseline_cost
        *
        100
        if baseline_cost > 0
        else 0
    )


    result_cols = st.columns(
        5,
        gap="small"
    )


    result_items = [

        (
            "ESTIMATED SAVING",
            f"₹{saving:,.0f}",
            "green"
        ),

        (
            "SAVING VS BASELINE",
            f"{saving_pct:+.1f}%",
            "green"
        ),

        (
            "OPTIMIZED COST",
            f"₹{total_cost:,.0f}",
            "cyan"
        ),

        (
            "AVG TRAVEL TIME",
            f"{average_time:.1f} min",
            "orange"
        ),

        (
            "WAREHOUSES",
            f"{len(st.session_state['warehouses']):02d}",
            "purple"
        ),

    ]


    for column, item in zip(
        result_cols,
        result_items
    ):

        with column:

            label, value, color = item

            st.html(
                f"""
<div class="result">

    <div class="result-label">
        {label}
    </div>

    <div class="result-value {color}">
        {value}
    </div>

</div>
"""
            )


    # ========================================================
    # BEFORE VS AFTER
    # ========================================================

    st.html(
        f"""
<div class="result-hero">

    <div class="result-hero-grid">

        <div class="result-hero-cell">
            <div class="result-hero-label">NETWORK IMPACT</div>
            <div class="result-hero-value">{saving_pct:+.1f}%</div>
            <div class="result-hero-note">
                modeled cost change compared with the demand-weighted baseline.
            </div>
        </div>

        <div class="result-hero-cell">
            <div class="result-hero-label">BASELINE → OPTIMIZED COST</div>
            <div class="result-hero-value" style="color:#05d9e8;">₹{baseline_cost:,.0f} → ₹{total_cost:,.0f}</div>
            <div class="result-hero-note">
                estimated delivery cost using the configured cost per kilometer.
            </div>
        </div>

        <div class="result-hero-cell">
            <div class="result-hero-label">DELIVERY DISTANCE</div>
            <div class="result-hero-value" style="color:#b967ff;">{total_distance:.1f} km</div>
            <div class="result-hero-note">
                total physical distance across the assigned neighborhoods.
            </div>
        </div>

    </div>

</div>
"""
    )


    # ========================================================
    # WAREHOUSE LOCATIONS
    # ========================================================

    st.html("""
    <div class="section-kicker">
        03 / FACILITY PLAN
    </div>

    <div class="section-heading">
        Recommended warehouse locations
    </div>

    <div class="section-rule"></div>
    """)


    warehouse_orders = {}


    for assignment in (
        st.session_state[
            "assignments"
        ]
    ):

        name = assignment[
            "Warehouse"
        ]

        warehouse_orders[
            name
        ] = (
            warehouse_orders.get(
                name,
                0
            )
            +
            assignment[
                "Orders"
            ]
        )


    warehouse_cols = st.columns(
        len(
            st.session_state[
                "warehouses"
            ]
        ),
        gap="small"
    )


    for i, (column, warehouse) in enumerate(
        zip(
            warehouse_cols,
            st.session_state[
                "warehouses"
            ]
        )
    ):

        name = warehouse[
            "Neighborhood"
        ]

        orders = warehouse_orders.get(
            name,
            0
        )


        with column:

            st.html(
                f"""
<div class="warehouse">

    <div class="warehouse-id">
        WAREHOUSE {i + 1:02d}
    </div>

    <div class="warehouse-name">
        🏭 {name}
    </div>

    <div class="warehouse-meta">
        LAT {warehouse["Latitude"]:.5f}
        ·
        LON {warehouse["Longitude"]:.5f}
    </div>

    <div
        style="
        margin-top:10px;
        color:#6b7a99;
        font-family:'IBM Plex Mono';
        font-size:7px;
        "
    >
        ASSIGNED DEMAND
    </div>

    <div
        style="
        margin-top:3px;
        color:#39ff8c;
        font-family:'IBM Plex Mono';
        font-size:17px;
        font-weight:700;
        "
    >
        {int(orders):,}
    </div>

    <div
        style="
        color:#6b7a99;
        font-family:'IBM Plex Mono';
        font-size:6px;
        "
    >
        ORDERS / DAY
    </div>

</div>
"""
            )


    # ========================================================
    # CHARTS
    # ========================================================

    st.html("""
    <div class="section-kicker">
        04 / PERFORMANCE ANALYTICS
    </div>

    <div class="section-heading">
        Cost and warehouse utilization
    </div>

    <div class="section-rule"></div>
    """)


    chart1, chart2 = st.columns(
        2,
        gap="small"
    )


    with chart1:

        fig = go.Figure()


        fig.add_trace(
            go.Bar(

                x=[
                    "BASELINE",
                    "OPTIMIZED"
                ],

                y=[
                    baseline_cost,
                    total_cost
                ],

                text=[
                    f"₹{baseline_cost:,.0f}",
                    f"₹{total_cost:,.0f}"
                ],

                textposition="outside",

                marker=dict(
                    color=[
                        "#ffb800",
                        "#05d9e8"
                    ]
                ),

            )
        )


        fig.update_layout(

            title="DELIVERY COST",

            height=380,

            margin=dict(
                l=15,
                r=15,
                t=50,
                b=20
            ),

            paper_bgcolor=
            "rgba(0,0,0,0)",

            plot_bgcolor=
            "rgba(0,0,0,0)",

            font=dict(
                family="IBM Plex Mono",
                color="#a9b7c5",
                size=8
            ),

            yaxis=dict(
                gridcolor=
                "rgba(5,217,232,.08)",
                zeroline=False
            ),

            xaxis=dict(
                showgrid=False
            ),

            showlegend=False,

        )


        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displayModeBar": False
            }
        )


    with chart2:

        load = (
            pd.DataFrame(
                st.session_state[
                    "assignments"
                ]
            )
            .groupby(
                "Warehouse"
            )[
                "Orders"
            ]
            .sum()
        )


        fig2 = go.Figure()


        fig2.add_trace(
            go.Bar(

                x=list(
                    load.index
                ),

                y=list(
                    load.values
                ),

                text=[
                    f"{int(x):,}"
                    for x in load.values
                ],

                textposition="outside",

                marker=dict(
                    color=[
                        "#05d9e8",
                        "#ff2a6d",
                        "#ffb800",
                        "#b967ff",
                        "#39ff8c"
                    ][
                        :len(load)
                    ]
                ),

            )
        )


        fig2.update_layout(

            title="WAREHOUSE LOAD",

            height=380,

            margin=dict(
                l=15,
                r=15,
                t=50,
                b=20
            ),

            paper_bgcolor=
            "rgba(0,0,0,0)",

            plot_bgcolor=
            "rgba(0,0,0,0)",

            font=dict(
                family="IBM Plex Mono",
                color="#a9b7c5",
                size=8
            ),

            yaxis=dict(
                gridcolor=
                "rgba(5,217,232,.08)",
                zeroline=False
            ),

            xaxis=dict(
                showgrid=False
            ),

            showlegend=False,

        )


        st.plotly_chart(
            fig2,
            use_container_width=True,
            config={
                "displayModeBar": False
            }
        )


    # ========================================================
    # ASSIGNMENT TABLE
    # ========================================================

    st.html("""
    <div class="section-kicker">
        05 / DELIVERY MATRIX
    </div>

    <div class="section-heading">
        Neighborhood assignments
    </div>

    <div class="section-rule"></div>
    """)


    assignments_df = pd.DataFrame(
        st.session_state[
            "assignments"
        ]
    )


    for column in [
        "Distance_km",
        "Weighted_Distance",
        "Delivery_Cost"
    ]:

        assignments_df[
            column
        ] = (
            assignments_df[
                column
            ].round(2)
        )


    st.dataframe(
        assignments_df,
        use_container_width=True,
        hide_index=True,
        height=420,
    )


    # ========================================================
    # MODEL ASSUMPTIONS
    # ========================================================

    st.html("""
    <div class="section-kicker">
        06 / MODEL ASSUMPTIONS
    </div>

    <div class="section-heading">
        What the optimization is actually measuring
    </div>

    <div class="section-rule"></div>

    <div class="assumption-grid">

        <div class="assumption-card">
            <div class="assumption-title">DISTANCE MODEL</div>
            <div class="assumption-copy">
                Geographic distance is calculated from latitude/longitude coordinates using the Haversine formula. It is not live road routing.
            </div>
        </div>

        <div class="assumption-card">
            <div class="assumption-title">COST MODEL</div>
            <div class="assumption-copy">
                Modeled delivery cost = distance × daily orders × configured cost per kilometer. Higher-demand neighborhoods therefore carry more weight.
            </div>
        </div>

        <div class="assumption-card">
            <div class="assumption-title">TIME MODEL</div>
            <div class="assumption-copy">
                Average travel time is estimated from weighted distance and the assumed vehicle speed. Traffic, signals and road conditions are not modeled.
            </div>
        </div>

        <div class="assumption-card">
            <div class="assumption-title">BASELINE</div>
            <div class="assumption-copy">
                The baseline uses a demand-weighted geographic center. It is an unconstrained comparison point, not a live warehouse recommendation.
            </div>
        </div>

        <div class="assumption-card">
            <div class="assumption-title">CONSTRAINTS</div>
            <div class="assumption-copy">
                Radius and capacity constraints are enforced during feasibility checks. Each neighborhood is assigned wholly to one selected warehouse.
            </div>
        </div>

        <div class="assumption-card">
            <div class="assumption-title">INTERPRETATION</div>
            <div class="assumption-copy">
                Results are planning estimates for comparing candidate networks. Real deployment should validate road distances, traffic, property cost and operating constraints.
            </div>
        </div>

    </div>

    <div class="demo-note">
        <strong style="color:#ffb800;">IMPORTANT ·</strong> The optimized locations are selected from the neighborhood coordinates in the supplied dataset. GRIDPOINT does not search arbitrary land parcels or live property listings.
    </div>
    """)


# ============================================================
# FOOTER
# ============================================================

st.html("""
<div class="footer">

    <div>
        GRIDPOINT // LOGISTICS INTELLIGENCE ENGINE
    </div>

    <div>
        DEMAND · GEOGRAPHY · COST · CAPACITY
    </div>

</div>
""")