import json
from typing import Dict, List

import streamlit as st


def _tr(lang: str, key: str) -> str:
    pack = {
        "English": {
            "title": "Hero Bikes & Scooters",
            "subtitle": "Browse Hero two-wheelers with language support, color options, features, and quick specs.",
            "search": "Search model",
            "category": "Category",
            "all": "All",
            "scooter": "Scooter",
            "motorcycle": "Motorcycle",
            "show_specs": "Show full specifications",
            "colors": "Colors",
            "features": "Features",
            "specs": "Specifications",
            "count": "Models found",
            "no_match": "No models matched your search.",
            "source_note": "Starter data based on verified official Hero pages. Add more models the same way.",
        },
        "Tamil": {
            "title": "Hero Bike & Scooter Page",
            "subtitle": "Hero வண்டிகளை language support உடன் color, feature, spec எல்லாம் பார்க்கலாம்.",
            "search": "Model தேடு",
            "category": "Category",
            "all": "அனைத்தும்",
            "scooter": "ஸ்கூட்டர்",
            "motorcycle": "மோட்டார் சைக்கிள்",
            "show_specs": "முழு விவரங்கள் காண்பி",
            "colors": "நிறங்கள்",
            "features": "சிறப்பம்சங்கள்",
            "specs": "விவரக்குறிப்புகள்",
            "count": "கண்டுபிடிக்கப்பட்ட models",
            "no_match": "உங்கள் தேடலுக்கு பொருந்தும் model இல்லை.",
            "source_note": "இது verified official Hero pages அடிப்படையிலான starter data. இதே மாதிரி மேலும் models சேர்க்கலாம்.",
        },
        "Thanglish": {
            "title": "Hero Bike & Scooter Page",
            "subtitle": "Hero vandi details-a language support oda color, feature, spec ellam paakalaam.",
            "search": "Model thedu",
            "category": "Category",
            "all": "Ellaam",
            "scooter": "Scooter",
            "motorcycle": "Bike",
            "show_specs": "Full details kaattu",
            "colors": "Colors",
            "features": "Features",
            "specs": "Specifications",
            "count": "Kedaicha models",
            "no_match": "Search-ku match aana model illa.",
            "source_note": "Idhu verified official Hero pages base pannina starter data. Idhe style-la innum models add pannalaam.",
        },
    }
    return pack.get(lang, pack["English"]).get(key, key)


def _pick(lang: str, data: Dict[str, str], fallback: str = "") -> str:
    return data.get(lang) or data.get("English") or fallback


def _matches(model: Dict, query: str, category: str) -> bool:
    q = (query or "").strip().lower()
    if category != "All" and model["category"] != category:
        return False
    if not q:
        return True
    blob = " ".join(
        [
            model["name"],
            model["category"],
            model.get("engine", ""),
            model.get("summary", {}).get("English", ""),
            " ".join(model.get("colors", [])),
            " ".join(model.get("features", {}).get("English", [])),
            " ".join(model.get("specs", {}).keys()),
        ]
    ).lower()
    return q in blob


BIKES: List[Dict] = [
    {
        "name": "Destini 110",
        "category": "Scooter",
        "engine": "110 cc",
        "summary": {
            "English": "A comfortable family scooter for daily commuting.",
            "Tamil": "Daily ride-kku comfortable family scooter.",
            "Thanglish": "Daily commute-ku comfortable family scooter.",
        },
        "colors": ["See official page for current colour options"],
        "features": {
            "English": ["Practical family scooter", "Smooth city ride focus", "Good daily usability"],
            "Tamil": ["குடும்ப பயன்பாட்டுக்கு ஏற்றது", "City ride-ku smooth", "Daily use-ku practical"],
            "Thanglish": ["Family use-ku nalla scooter", "City-la smooth ride", "Daily use-ku practical"],
        },
        "specs": {"Engine": "110 cc", "Mileage": "56.2 kmpl", "Fuel Tank": "5.3 L", "Official Page": "https://www.heromotocorp.com/en-in/scooters/destini-110.html"},
    },
    {
        "name": "New Destini 125",
        "category": "Scooter",
        "engine": "125 cc",
        "summary": {"English": "An elegant and practical 125 cc family scooter.", "Tamil": "Elegant ஆன 125 cc family scooter.", "Thanglish": "Elegant 125 cc family scooter."},
        "colors": ["Candy Blazing Red", "Pearl Fadeless White", "Pearl Black"],
        "features": {"English": ["Smooth performance", "Practical commuting", "Modern styling"], "Tamil": ["Smooth performance", "Daily commuting-ku useful", "Modern styling"], "Thanglish": ["Smooth performance", "Daily commuting-ku useful", "Modern look"]},
        "specs": {"Engine": "125 cc", "Color Options": "Candy Blazing Red / Pearl Fadeless White / Pearl Black", "Official Page": "https://www.heromotocorp.com/en-in/scooters/new-destini-125.html"},
    },
    {
        "name": "Destini Prime",
        "category": "Scooter",
        "engine": "124.6 cc",
        "summary": {"English": "A refined scooter for comfortable everyday riding.", "Tamil": "Comfortable everyday riding-kku refined scooter.", "Thanglish": "Comfortable everyday riding-ku refined scooter."},
        "colors": ["See official page for latest colour options"],
        "features": {"English": ["Daily commute friendly", "Comfort-oriented", "Refined performance"], "Tamil": ["Daily commute-ku friendly", "Comfort focus", "Refined performance"], "Thanglish": ["Daily commute-friendly", "Comfort focus", "Refined performance"]},
        "specs": {"Engine": "124.6 cc", "Official Page": "https://www.heromotocorp.com/en-in/scooters/destini-prime.html"},
    },
    {
        "name": "Xoom 110",
        "category": "Scooter",
        "engine": "110.9 cc",
        "summary": {"English": "A sporty scooter with sharp styling and smart features.", "Tamil": "Sharp styling & smart features oda sporty scooter.", "Thanglish": "Sharp styling and smart features oda sporty scooter."},
        "colors": ["Black", "Polestar Blue", "Moon Yellow"],
        "features": {"English": ["Sporty design", "Smart features", "Fun city ride"], "Tamil": ["Sporty design", "Smart features", "City ride fun-a irukkum"], "Thanglish": ["Sporty design", "Smart features", "City ride fun-a irukkum"]},
        "specs": {"Engine": "110.9 cc", "Color Options": "Black / Polestar Blue / Moon Yellow", "Official Page": "https://www.heromotocorp.com/en-in/scooters/xoom.html"},
    },
    {
        "name": "Xoom 125",
        "category": "Scooter",
        "engine": "124.6 cc",
        "summary": {"English": "A sporty 125 cc scooter with quick response.", "Tamil": "Quick response kudukkura sporty 125 cc scooter.", "Thanglish": "Quick response kudukkura sporty 125 cc scooter."},
        "colors": ["MATTE GREY", "VIBRANT BLUE METALIC"],
        "features": {"English": ["Quick acceleration", "Smart features", "Stylish design"], "Tamil": ["Quick acceleration", "Smart features", "Stylish design"], "Thanglish": ["Quick acceleration", "Smart features", "Stylish design"]},
        "specs": {"Engine": "124.6 cc", "Color Options": "MATTE GREY / VIBRANT BLUE METALIC", "Official Page": "https://www.heromotocorp.com/en-in/scooters/xoom-125.html"},
    },
    {
        "name": "Xoom 160",
        "category": "Scooter",
        "engine": "156 cc",
        "summary": {"English": "A premium sporty scooter in the Xoom family.", "Tamil": "Xoom family-la premium sporty scooter.", "Thanglish": "Xoom family-la premium sporty scooter."},
        "colors": ["See official page for current colour options"],
        "features": {"English": ["Premium sporty feel", "High engine capacity", "Modern styling"], "Tamil": ["Premium sporty feel", "High engine capacity", "Modern styling"], "Thanglish": ["Premium sporty feel", "High engine capacity", "Modern styling"]},
        "specs": {"Engine": "156 cc", "Official Page": "https://www.heromotocorp.com/en-in.html"},
    },
    {
        "name": "Pleasure+ XTEC",
        "category": "Scooter",
        "engine": "110.9 cc",
        "summary": {"English": "A stylish scooter with commuter-friendly everyday use.", "Tamil": "Commuter-friendly stylish scooter.", "Thanglish": "Commuter-friendly stylish scooter."},
        "colors": ["See official page for latest colour options"],
        "features": {"English": ["Light and easy ride", "Daily city commuting", "Practical design"], "Tamil": ["Light and easy ride", "Daily city commuting", "Practical design"], "Thanglish": ["Light and easy ride", "Daily city commuting", "Practical design"]},
        "specs": {"Engine": "110.9 cc", "Official Page": "https://www.heromotocorp.com/en-in.html"},
    },
    {
        "name": "Xtreme 125R",
        "category": "Motorcycle",
        "engine": "125 cc",
        "summary": {"English": "A sporty 125 cc motorcycle with quick acceleration.", "Tamil": "Quick acceleration oda sporty 125 cc motorcycle.", "Thanglish": "Quick acceleration oda sporty 125 cc motorcycle."},
        "colors": ["See official page for current colour options"],
        "features": {"English": ["5.7 sec 0-60 km/h acceleration", "Smart sporty styling", "Strong road presence"], "Tamil": ["0-60 km/h 5.7 sec acceleration", "Smart sporty styling", "Road-la strong presence"], "Thanglish": ["0-60 km/h 5.7 sec acceleration", "Smart sporty styling", "Road-la strong presence"]},
        "specs": {"Engine": "125 cc", "Power": "11.4 BHP @ 8250 RPM", "Torque": "10.5 Nm @ 6500 RPM", "Acceleration": "5.7 sec (0-60 km/h)", "Official Page": "https://www.heromotocorp.com/en-in/motorcycles/executive/xtreme-125r.html"},
    },
    {
        "name": "Super Splendor XTEC",
        "category": "Motorcycle",
        "engine": "125 cc",
        "summary": {"English": "A practical commuter motorcycle with digital console.", "Tamil": "Digital console oda practical commuter motorcycle.", "Thanglish": "Digital console oda practical commuter motorcycle."},
        "colors": ["See official page for current colour options"],
        "features": {"English": ["Digital console", "Comfortable commuting", "Trusted daily ride"], "Tamil": ["Digital console", "Comfortable commuting", "Trusted daily ride"], "Thanglish": ["Digital console", "Comfortable commuting", "Trusted daily ride"]},
        "specs": {"Engine": "124.7 cc / 125 cc class", "Torque": "10.6 Nm @ 6000 RPM", "Official Page": "https://www.heromotocorp.com/en-in/motorcycles/executive/super-splendor-xtec.html"},
    },
    {
        "name": "Glamour",
        "category": "Motorcycle",
        "engine": "125 cc",
        "summary": {"English": "A reliable commuter with stylish everyday appeal.", "Tamil": "Stylish everyday appeal oda reliable commuter.", "Thanglish": "Stylish everyday appeal oda reliable commuter."},
        "colors": ["See official page for current colour options"],
        "features": {"English": ["Commuter friendly", "Stylish design", "Balanced performance"], "Tamil": ["Commuter friendly", "Stylish design", "Balanced performance"], "Thanglish": ["Commuter friendly", "Stylish design", "Balanced performance"]},
        "specs": {"Engine": "125 cc", "Official Page": "https://www.heromotocorp.com/en-in/motorcycles/executive/glamour.html"},
    },
    {
        "name": "HF 100",
        "category": "Motorcycle",
        "engine": "97.2 cc",
        "summary": {"English": "A practical and fuel-efficient daily commuter.", "Tamil": "Fuel-efficient daily commuter.", "Thanglish": "Fuel-efficient daily commuter."},
        "colors": ["See official page for current colour options"],
        "features": {"English": ["Excellent fuel efficiency", "Affordable commuting", "Simple and dependable"], "Tamil": ["Excellent fuel efficiency", "Affordable commuting", "Simple and dependable"], "Thanglish": ["Excellent fuel efficiency", "Affordable commuting", "Simple and dependable"]},
        "specs": {"Engine": "97.2 cc", "Official Page": "https://www.heromotocorp.com/en-in/motorcycles/practical/hf-100.html"},
    },
    {
        "name": "Xtreme 250R",
        "category": "Motorcycle",
        "engine": "250 cc",
        "summary": {"English": "A performance-oriented Hero motorcycle.", "Tamil": "Performance-oriented Hero motorcycle.", "Thanglish": "Performance-oriented Hero motorcycle."},
        "colors": ["See official page for current colour options"],
        "features": {"English": ["Performance-oriented", "Sporty ride", "Premium look"], "Tamil": ["Performance-oriented", "Sporty ride", "Premium look"], "Thanglish": ["Performance-oriented", "Sporty ride", "Premium look"]},
        "specs": {"Engine": "250 cc class", "Official Page": "https://www.heromotocorp.com/en-in/motorcycles.html"},
    },
    {
        "name": "Karizma XMR",
        "category": "Motorcycle",
        "engine": "210 cc",
        "summary": {"English": "A sporty premium motorcycle in the Hero range.", "Tamil": "Hero range-la sporty premium motorcycle.", "Thanglish": "Hero range-la sporty premium motorcycle."},
        "colors": ["See official page for current colour options"],
        "features": {"English": ["Sporty premium design", "Control-focused ride", "Racing-inspired feel"], "Tamil": ["Sporty premium design", "Control-focused ride", "Racing-inspired feel"], "Thanglish": ["Sporty premium design", "Control-focused ride", "Racing-inspired feel"]},
        "specs": {"Engine": "210 cc class", "Official Page": "https://www.heromotocorp.com/en-in/motorcycles.html"},
    },
]


def page_hero_bikes():
    st.markdown(
        """
        <style>
        .bike-hero {
            padding: 18px 20px;
            border-radius: 22px;
            background: linear-gradient(135deg, #111827, #e31837);
            color: white;
            margin-bottom: 16px;
        }
        .bike-hero h1 { margin: 0; font-size: 28px; font-weight: 900; }
        .bike-hero p { margin: 6px 0 0 0; color: #fee2e2; }
        .bike-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 20px;
            padding: 16px;
            box-shadow: 0 12px 30px rgba(15,23,42,.08);
            height: 100%;
            margin-bottom: 12px;
        }
        .chip {
            display:inline-block;
            padding: 5px 10px;
            border-radius: 999px;
            background: #fee2e2;
            color: #991b1b;
            font-size: 12px;
            font-weight: 800;
            margin-right: 6px;
            margin-bottom: 6px;
        }
        .spec-box {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 10px 12px;
            margin-top: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "hero_bikes_lang" not in st.session_state:
        st.session_state["hero_bikes_lang"] = "English"
    lang = st.sidebar.selectbox("Language", ["English", "Tamil", "Thanglish"], index=0, key="hero_bikes_lang")
    

    st.markdown(
        f"""
        <div class="bike-hero">
            <h1>{_tr(lang, "title")}</h1>
            <p>{_tr(lang, "subtitle")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([2, 1])
    with c1:
        query = st.text_input(_tr(lang, "search"), placeholder="Destini / Xoom / Glamour / Xtreme...", key="hero_bikes_search")
    with c2:
        category_label = st.selectbox(
            _tr(lang, "category"),
            [_tr(lang, "all"), _tr(lang, "scooter"), _tr(lang, "motorcycle")],
            key="hero_bikes_category"
        )

    cat_map = {_tr(lang, "all"): "All", _tr(lang, "scooter"): "Scooter", _tr(lang, "motorcycle"): "Motorcycle"}
    category = cat_map.get(category_label, "All")

    models = [m for m in BIKES if _matches(m, query, category)]
    st.caption(f"{_tr(lang, 'count')}: {len(models)}")
    st.caption(_tr(lang, "source_note"))

    if not models:
        st.error(_tr(lang, "no_match"))
        return

    s1, s2, s3 = st.columns(3)
    s1.metric(_tr(lang, "all"), len(models))
    s2.metric(_tr(lang, "scooter"), len([m for m in models if m["category"] == "Scooter"]))
    s3.metric(_tr(lang, "motorcycle"), len([m for m in models if m["category"] == "Motorcycle"]))

    show_specs = st.toggle(_tr(lang, "show_specs"), value=False, key="hero_bikes_toggle")

    for i in range(0, len(models), 3):
        row = st.columns(3)
        for j, model in enumerate(models[i:i+3]):
            with row[j]:
                st.markdown('<div class="bike-card">', unsafe_allow_html=True)
                st.subheader(model["name"])
                st.caption(f"{model['category']} • {model['engine']}")
                st.write(_pick(lang, model["summary"]))

                st.markdown(f"**{_tr(lang, 'features')}**")
                for feat in model["features"].get(lang, model["features"]["English"]):
                    st.write(f"• {feat}")

                st.markdown(f"**{_tr(lang, 'colors')}**")
                colors = model.get("colors", [])
                for color in colors[:4]:
                    st.markdown(f"<span class='chip'>{color}</span>", unsafe_allow_html=True)

                if show_specs:
                    st.markdown(f"<div class='spec-box'><b>{_tr(lang, 'specs')}</b></div>", unsafe_allow_html=True)
                    st.json(model.get("specs", {}), expanded=False)

                st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    st.markdown("### Quick data export")
    st.download_button(
        "Download models as JSON",
        data=json.dumps(BIKES, indent=2, ensure_ascii=False),
        file_name="hero_bikes_data.json",
        mime="application/json",
        use_container_width=True,
    )


if __name__ == "__main__":
    page_hero_bikes()
